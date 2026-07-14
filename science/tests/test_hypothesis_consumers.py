"""The consumers that read the hypothesis vocabulary — after the fold.

Every consumer that asked "is this hypothesis still live?" was reading a `status` field that held
the epistemic VERDICT. The verdict moved to `verdict` and the lifecycle moved into `status`, so each
of these had to be re-pointed. The tests that matter here are the ones that pin what did NOT move:
the QUESTION vocabulary, which still encodes answeredness in `status` because the question slice has
not run. A consumer rewritten across kind boundaries would silently reopen every answered question
in the corpus.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
import yaml

from click.testing import CliRunner

from science_tool.consolidation import _prepare_supersession, mark_superseded
from science_tool.entities_cli import entity_group
from science_tool.entities import EntityCommandError, edit_entity, find_entity
from science_tool.graph.attention import DEBT_QUESTION_STATUSES
from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks.dataset_capabilities import is_demand_closed

SRC = Path(__file__).resolve().parents[1] / "src"


def test_demand_closed_reads_the_hypothesis_VERDICT_now() -> None:
    # `refuted` was the ONLY hypothesis-specific value any consumer read. It is a verdict now.
    assert is_demand_closed(kind="hypothesis", status="active", verdict="refuted") is True
    assert is_demand_closed(kind="hypothesis", status="active", verdict="supported") is False
    assert is_demand_closed(kind="hypothesis", status="retired", verdict=None) is True


def test_a_REFUTED_hypothesis_that_is_still_being_WORKED_is_not_closed_by_its_LIFECYCLE() -> None:
    # The two axes, and the cell that proves they are two. `refuted` + `active` is a real state --
    # disproved, still being written up. It is demand-CLOSED (the claim needs no more data) and
    # lifecycle-OPEN (somebody is still working on it), and no single field could say both.
    assert is_demand_closed(kind="hypothesis", status="active", verdict="refuted") is True
    from science_tool.entities import CLOSED_LIFECYCLE_STATUSES

    assert "active" not in CLOSED_LIFECYCLE_STATUSES
    assert "refuted" not in CLOSED_LIFECYCLE_STATUSES  # a VERDICT is never a lifecycle state


def test_QUESTION_demand_closure_is_UNCHANGED() -> None:
    # The question slice has not happened. Its statuses still carry answeredness, and this predicate
    # must keep reading them exactly as it does today.
    assert is_demand_closed(kind="question", status="answered", verdict=None) is True
    assert is_demand_closed(kind="question", status="active", verdict=None) is False
    # ...and the residual-demand states stay LIVE, as they were.
    assert is_demand_closed(kind="question", status="partially-answered", verdict=None) is False
    assert is_demand_closed(kind="question", status="deferred", verdict=None) is False


def test_a_question_is_not_read_through_the_HYPOTHESIS_rules() -> None:
    # The failure mode the kind split exists to prevent. `answered` is not a lifecycle word and it is
    # not a verdict -- if the hypothesis branch were applied to a question, an answered question
    # would come back LIVE and every one in the corpus would silently reopen.
    assert is_demand_closed(kind="question", status="answered", verdict=None) is True
    assert is_demand_closed(kind="hypothesis", status="answered", verdict=None) is False


def test_question_debt_is_untouched() -> None:
    assert DEBT_QUESTION_STATUSES == frozenset({"active", "partially-answered", "deferred"})


# ---------------------------------------------------------------------------------------------
# THE WRITE BOUNDARY. The consumers above READ the new vocabulary; these pin who may WRITE it.
# ---------------------------------------------------------------------------------------------


def _hypothesis(root: Path, slug: str, **fields: object) -> Path:
    frontmatter: dict[str, object] = {
        "id": f"hypothesis:{slug}",
        "kind": "hypothesis",
        "title": f"H {slug}",
        "status": "active",
        "created": "2026-07-01",
        "updated": "2026-07-01",
    }
    frontmatter.update(fields)
    path = root / "entities/hypotheses" / f"{slug}.md"
    path.write_text(
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\nBody.\n", encoding="utf-8"
    )
    return path


def _frontmatter(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---\n")[1])


@pytest.fixture
def project(tmp_path: Path) -> Path:
    # PINNED. The schema is enforced on writes only where the project DECLARED that it speaks
    # schema 2 -- the same gate the loader uses, because "does this project speak schema 2?" gets
    # exactly one answer (`load_project_schema_if_pinned`).
    (tmp_path / "science.yaml").write_text(
        yaml.safe_dump({"name": "p", "id": "p", "entity_schema_version": 2}), encoding="utf-8"
    )
    (tmp_path / "entities/hypotheses").mkdir(parents=True)
    _hypothesis(tmp_path, "0001-x")
    _hypothesis(tmp_path, "0002-y")
    return tmp_path


def test_edit_status_is_the_lifecycle_boundary(project: Path) -> None:
    # ONE generic boundary, not four invented verbs. It schema-validates the TARGET state, takes the
    # basis ATOMICALLY with the transition, and FAILS BEFORE WRITING -- the file is untouched, not
    # half-transitioned with a validate WARN filed against it.
    with pytest.raises(EntityCommandError, match="closure_basis"):
        edit_entity(project, "hypothesis:0001-x", status="retired")
    assert _frontmatter(project / "entities/hypotheses/0001-x.md")["status"] == "active"

    edit_entity(project, "hypothesis:0001-x", status="retired", closure_basis="no samples left")
    written = _frontmatter(project / "entities/hypotheses/0001-x.md")
    assert written["status"] == "retired"
    assert written["closure_basis"] == "no samples left"


def test_a_CONCLUSION_needs_something_concluded(project: Path) -> None:
    # `complete` is the lifecycle saying the work finished. The schema refuses it without a verdict,
    # because admitting `complete` + absent-verdict would give `retired + closure_basis` a second
    # spelling that reads, to every consumer, as though the hypothesis had been RESOLVED.
    with pytest.raises(EntityCommandError, match="verdict"):
        edit_entity(project, "hypothesis:0001-x", status="complete")

    edit_entity(project, "hypothesis:0001-x", status="complete", verdict="refuted")
    written = _frontmatter(project / "entities/hypotheses/0001-x.md")
    assert (written["status"], written["verdict"]) == ("complete", "refuted")


def test_edit_entity_refuses_a_DANGLING_successor(project: Path) -> None:
    # The schema validates ONE record, so it can only see that a successor is PRESENT. Whether it
    # RESOLVES is a cross-record fact, and this is the write-boundary call site of the checker that
    # asks it (`check_resolution`).
    #
    # THE LINEAGE FIELD IS `resynthesized_into`, NOT `superseded_by` -- and that is not a detail.
    # `superseded_by` is DERIVED, and there is no parameter on any writer that could carry a dangling
    # one to this boundary: `_prepare_supersession` reads it from an ADMITTED canonical edge. So
    # `resynthesized_into` is the one lineage field a human can dangle, and therefore the only one
    # this guard can be written against. A guard aimed at an unreachable case is decoration.
    with pytest.raises(EntityCommandError, match="9999-nope"):
        edit_entity(
            project,
            "hypothesis:0001-x",
            status="superseded",
            resynthesized_into=["hypothesis:9999-nope"],
        )
    assert _frontmatter(project / "entities/hypotheses/0001-x.md")["status"] == "active"

    # ...and it is the RESOLUTION that was wrong, not the shape: the same write to a real, live,
    # OTHER hypothesis goes through.
    edit_entity(
        project, "hypothesis:0001-x", status="superseded", resynthesized_into=["hypothesis:0002-y"]
    )
    assert _frontmatter(project / "entities/hypotheses/0001-x.md")["status"] == "superseded"


def test_an_entity_cannot_be_its_own_successor(project: Path) -> None:
    # Resolvable, live, a hypothesis -- and a closed loop. The record would report a reason for its
    # own closure that is itself.
    with pytest.raises(EntityCommandError, match="itself"):
        edit_entity(
            project,
            "hypothesis:0001-x",
            status="superseded",
            resynthesized_into=["hypothesis:0001-x"],
        )


def test_no_writer_can_be_HANDED_a_groundless_lineage(project: Path) -> None:
    # An earlier draft of this test PERFORMED the violation and asserted the boundary refused it. It
    # passed -- and it was the bug: to assert the guard, the test had to be ABLE to pass the derived
    # fact as caller input. A resolvable id with no canonical edge behind it satisfies the schema AND
    # the resolution check, and the supersession is grounded in nothing.
    #
    # So this test requires the CALL ITSELF to be impossible. And it forbids the `**kwargs` that
    # would silently un-assert everything below it: the absence of a named parameter is exactly what
    # a VAR_KEYWORD signature guarantees, whether or not the field is reachable.
    with pytest.raises(TypeError):
        edit_entity(
            project,
            "hypothesis:0001-x",
            superseded_by="hypothesis:0002-y",  # type: ignore[call-arg]  # RESOLVABLE. Still groundless.
        )

    for fn in (edit_entity, _prepare_supersession):
        params = inspect.signature(fn).parameters
        assert "superseded_by" not in params
        assert not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()), (
            f"{fn.__name__} grew a **kwargs -- which reopens the door AND makes the assertion above "
            f"vacuous. The unrestricted mechanism is `entities._prepare_write`, and it is private "
            f"for exactly this reason."
        )


def _call_sites(target: str) -> set[tuple[str, str]]:
    """Every (module, enclosing function) that CALLS `target`, by AST.

    An earlier draft grepped for the substring and asserted the set of FILES containing it. That
    proves nothing it claims: a docstring mentioning the name counts as a caller, a module that
    imports it and never calls it counts as a caller, and -- the reason it actually fails -- a SECOND
    function inside an already-listed file counts as nothing, because the file was already in the
    set. The guard could not see the violation it exists to see. Match the call, and name the caller.
    """
    sites: set[tuple[str, str]] = set()
    for path in (SRC / "science_tool").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for enclosing in ast.walk(tree):
            if not isinstance(enclosing, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for node in ast.walk(enclosing):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else None
                )
                if name == target:
                    sites.add((path.name, enclosing.name))
    return sites


def test_the_unrestricted_MECHANISM_has_exactly_the_call_sites_we_sanctioned() -> None:
    # `_prepare_write(project_root, ref, fields: Mapping)` CAN set `superseded_by` -- it is the
    # mechanism, and a mechanism that could not set a derived field would be useless to the thing
    # that derives it. The guarantee is not that it refuses; it is that the only caller supplying
    # that key is the one that DERIVES it from an admitted edge. So pin the call sites BY NAME: a
    # third one is how this arrangement would quietly stop being true.
    assert _call_sites("_prepare_write") == {
        ("entities.py", "edit_entity"),  # authored -- cannot express the field
        ("consolidation.py", "_prepare_supersession"),  # derived -- reads it off the graph
    }


def test_the_COMMIT_half_has_exactly_the_call_sites_we_sanctioned() -> None:
    # `_commit_write` repeats no schema or resolution decision -- by contract. It re-verifies the
    # SEAL: the proof that those decisions covered THESE bytes for THIS path. `mark_superseded` is a
    # sanctioned caller because it commits a batch `_prepare_supersession` prepared.
    assert _call_sites("_commit_write") == {
        ("entities.py", "edit_entity"),
        ("consolidation.py", "mark_superseded"),
    }


def test_the_OTHER_entity_writer_still_cannot_reach_a_hypothesis() -> None:
    # HONESTY ABOUT THE BOUNDARY'S REACH. `_prepare_write` is not the only thing in this tree that
    # rewrites entity frontmatter: `render_entity_frontmatter_updates` does too, it takes an
    # arbitrary `updates` mapping, it runs NO schema or resolution check -- and it writes
    # `superseded_by` and `resynthesized_into` outright (proposition_resynthesis_apply).
    #
    # It is not a hole TODAY because both its callers operate on PROPOSITIONS, and `proposition` is
    # not in the migration slice: no project mixin, so no schema to enforce and no lineage rule to
    # break. It becomes a hole the day a third caller points it at a hypothesis, or the day the
    # proposition slice runs -- and this is the test that will say so.
    assert _call_sites("render_entity_frontmatter_updates") == {
        ("proposition_resynthesis_apply.py", "_original_edit"),
        ("proposition_reconciliation_apply.py", "plan_canonicalization_apply"),
    }


def _corrupt(project_root: Path, slug: str, **fields: object) -> None:
    """Hand-edit an entity's frontmatter, BYPASSING every writer.

    It has to bypass them -- that is the state under test. `edit_entity` would refuse most of these,
    which is the point: this simulates a human with a text editor, or a file that predates a rule.
    """
    location = find_entity(project_root, f"hypothesis:{slug}")
    frontmatter = dict(location.frontmatter) | fields
    location.path.write_text(
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n{location.body}",
        encoding="utf-8",
    )


def test_a_CORRUPTED_inverse_is_caught_by_the_net_that_MATCHES_ITS_FAILURE(project: Path) -> None:
    # A hand-edited `superseded_by` is NOT caught at the write boundary -- nothing can hand one to a
    # writer, so no writer ever sees it. Saying "the boundary catches it" would be false. THREE
    # things catch it, and WHICH ONE depends on how it is wrong:
    #
    #   1. STALE (an edge exists, pointing elsewhere) -> `mark_superseded` RECONCILES it. `to_repair`.
    #   2. DANGLING (the id resolves to nothing)      -> `check_resolution`. A validate WARN.
    #   3. GROUNDLESS (resolves; NO edge behind it)   -> `unbacked_inverses`. Blocks apply.
    #
    # This test pins row 1. Rows 2 and 3 are pinned on the consolidation side.
    _corrupt(project, "0001-x", status="superseded", superseded_by="hypothesis:9999-nope")
    _corrupt(
        project,
        "0002-y",
        relations=[{"predicate": "sci:supersedes", "target": "hypothesis:0001-x"}],
    )

    report = mark_superseded(project, apply=True)

    assert report["repaired"] == ["hypothesis:0001-x"]
    # The EDGE won, not the hand edit.
    assert _frontmatter(project / "entities/hypotheses/0001-x.md")["superseded_by"] == "hypothesis:0002-y"


def test_the_AUTHORED_lineage_field_is_reachable_from_the_CLI(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ...and therefore the write-boundary lineage guard is not decoration. `edit_entity` grew a
    # `resynthesized_into` parameter with NO production caller -- zero uses in the corpus, no flag on
    # the CLI -- which would have made the guard above a rule enforced only against tests. The schema
    # discharges `superseded` with any of `superseded_by` (DERIVED), `closure_basis`, or
    # `resynthesized_into`; without this flag, a SPLIT supersession is a state the schema admits and
    # no writer in the toolkit can produce.
    monkeypatch.chdir(project)  # `entity edit` writes to the project it is standing in
    runner = CliRunner()
    dangling = runner.invoke(
        entity_group,
        ["edit", "hypothesis:0001-x", "--status", "superseded",
         "--resynthesized-into", "hypothesis:9999-nope"],
    )
    assert dangling.exit_code != 0
    assert "9999-nope" in dangling.output
    assert _frontmatter(project / "entities/hypotheses/0001-x.md")["status"] == "active"

    ok = runner.invoke(
        entity_group,
        ["edit", "hypothesis:0001-x", "--status", "superseded",
         "--resynthesized-into", "hypothesis:0002-y"],
    )
    assert ok.exit_code == 0, ok.output
    written = _frontmatter(project / "entities/hypotheses/0001-x.md")
    assert written["resynthesized_into"] == ["hypothesis:0002-y"]


def test_the_LINEAGE_guard_is_live_on_an_UNMIGRATED_project(tmp_path: Path) -> None:
    # THE ASYMMETRY, CERTIFIED. The SCHEMA check is gated on the pin; this one is NOT, and that is
    # deliberate: `superseded` meant `superseded` in the old vocabulary too, so a dangling successor
    # is authorable in an unmigrated project TODAY -- which is exactly the corpus that most needs the
    # guard. Gating it on the pin would arm it only for the projects already made safe.
    #
    # No `entity_schema_version` here. If this ever starts passing the write, the guard has quietly
    # become a reward for having already migrated.
    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "p", "id": "p"}), encoding="utf-8")
    (tmp_path / "entities/hypotheses").mkdir(parents=True)
    _hypothesis(tmp_path, "0001-x")

    with pytest.raises(EntityCommandError, match="9999-nope"):
        edit_entity(
            tmp_path,
            "hypothesis:0001-x",
            status="superseded",
            resynthesized_into=["hypothesis:9999-nope"],
        )

    # ...and the SCHEMA half is correctly silent here: `phase` is a key the 2.0 mixin REFUSES, but
    # this project never claimed to speak 2.0, so an unrelated edit to a file the migration has not
    # reached must still go through. Enforcing the new schema on an unpinned project would reject
    # `--title` over a key the migration is coming for.
    _hypothesis(tmp_path, "0002-y", phase="active", status="refuted")
    edit_entity(tmp_path, "hypothesis:0002-y", title="Renamed")
    assert _frontmatter(tmp_path / "entities/hypotheses/0002-y.md")["title"] == "Renamed"


# ---------------------------------------------------------------------------------------------
# THE FAIL-OPEN PATHS. Each of these was a gate that, when it could not decide, decided NOTHING.
# ---------------------------------------------------------------------------------------------


def test_a_MISSPELLED_pin_FAILS_instead_of_degrading_to_unpinned(tmp_path: Path) -> None:
    # ☠️ THE WORST SHAPE OF BUG THIS ARC HAS: a guard routed around by the code that needed it.
    # `reject_near_miss_keys` was written to catch exactly `entity_schema_verison`, and the write
    # boundary then read the pin straight off the raw YAML -- so the typo parsed as "no pin", every
    # schema check went silent, and the project sat there believing it had migrated. One transposed
    # letter turned the whole boundary off, and NOTHING said so.
    (tmp_path / "science.yaml").write_text(
        yaml.safe_dump({"name": "p", "id": "p", "entity_schema_verison": 2}), encoding="utf-8"
    )
    (tmp_path / "entities/hypotheses").mkdir(parents=True)
    _hypothesis(tmp_path, "0001-x")

    # It must not silently accept `complete` with no verdict, which is what "degraded to unpinned"
    # bought. It must REFUSE, and say the word the author typed wrong.
    with pytest.raises(EntityCommandError, match="entity_schema_verison"):
        edit_entity(tmp_path, "hypothesis:0001-x", status="complete")
    assert _frontmatter(tmp_path / "entities/hypotheses/0001-x.md")["status"] == "active"


def test_a_MISSPELLED_pin_FAILS_ON_THE_LOAD_PATH_TOO(tmp_path: Path) -> None:
    # The same fail-open, at the reader. The pin decides whether the LOADER enforces the schema at
    # all, so a near-miss pin would switch validation off and load an unvalidated corpus -- while its
    # author believed it was protected. The guard has to run on both paths or it protects neither.
    (tmp_path / "science.yaml").write_text(
        yaml.safe_dump({"name": "p", "id": "p", "entity_schema_verison": 2}), encoding="utf-8"
    )
    (tmp_path / "entities/hypotheses").mkdir(parents=True)
    _hypothesis(tmp_path, "0001-x")

    with pytest.raises(ValueError, match="entity_schema_verison"):
        load_project_sources(tmp_path)


def test_an_UNMIGRATED_project_is_refused_the_NEW_VOCABULARY(tmp_path: Path) -> None:
    # `verdict` and `closure_basis` MEAN NOTHING before the fold: under schema 1 the verdict IS
    # `status`, and there is no lifecycle for a closure to discharge. Writing one anyway produced a
    # record speaking two vocabularies at once -- `verdict: supported` sitting beside `status:
    # proposed` and `phase: active`, three fields with no agreement between them. That is the exact
    # state this arc exists to abolish, and the write surface was handing it out.
    #
    # "Not migrated" is not "no rules apply". It is "has not earned the new words yet".
    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "p", "id": "p"}), encoding="utf-8")
    (tmp_path / "entities/hypotheses").mkdir(parents=True)
    path = _hypothesis(tmp_path, "0001-x", status="proposed", phase="active")

    for field in ("verdict", "closure_basis"):
        with pytest.raises(EntityCommandError, match="migrate-hypothesis"):
            edit_entity(tmp_path, "hypothesis:0001-x", **{field: "supported"})
    written = _frontmatter(path)
    assert "verdict" not in written and "closure_basis" not in written

    # ...and the project is still WORKABLE. Refusing the new vocabulary must not refuse the old one:
    # a `--title` edit to a file the migration has not reached still goes through.
    edit_entity(tmp_path, "hypothesis:0001-x", title="Renamed")
    assert _frontmatter(path)["title"] == "Renamed"


def test_a_DANGLING_successor_on_an_OPEN_record_is_caught(tmp_path: Path) -> None:
    # THE TRIGGER ASKED THE WRONG QUESTION. It fired on `status == "superseded"` -- a proxy for "has
    # a successor" -- so an ACTIVE hypothesis naming `hypothesis:9999-nope` was never checked at all.
    # The one fault the module exists to catch, sailing through on a status.
    #
    # Unpinned on purpose: the schema (which would also refuse this now, via the reverse implication)
    # does not run here, so this pins the RESOLUTION check specifically.
    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "p", "id": "p"}), encoding="utf-8")
    (tmp_path / "entities/hypotheses").mkdir(parents=True)
    _hypothesis(tmp_path, "0001-x")

    with pytest.raises(EntityCommandError, match="9999-nope"):
        edit_entity(tmp_path, "hypothesis:0001-x", resynthesized_into=["hypothesis:9999-nope"])


def test_a_record_with_NO_lineage_does_not_pay_for_OTHER_entities_alias_collisions(
    tmp_path: Path,
) -> None:
    # THE SAME PROXY, FAILING THE OTHER WAY. A `superseded` record discharged by `closure_basis` has
    # no successor and nothing to resolve -- but the status-keyed trigger built a resolver for it
    # anyway, and `ReferenceResolver.from_entities` RAISES on a duplicated alias. So an unrelated
    # `--title` edit was blocked by a collision between two entities this record never mentions.
    #
    # The collision is real and still reportable; it is simply none of this write's business.
    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "p", "id": "p"}), encoding="utf-8")
    (tmp_path / "entities/hypotheses").mkdir(parents=True)
    _hypothesis(tmp_path, "0001-x", status="superseded", closure_basis="folded into the review")
    _hypothesis(tmp_path, "0002-y", aliases=["hypothesis:shared"])
    _hypothesis(tmp_path, "0003-z", aliases=["hypothesis:shared"])  # <- the collision

    edit_entity(tmp_path, "hypothesis:0001-x", title="Renamed")
    assert _frontmatter(tmp_path / "entities/hypotheses/0001-x.md")["title"] == "Renamed"
