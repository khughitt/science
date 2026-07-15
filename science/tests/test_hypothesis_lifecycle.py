"""`status` is the LIFECYCLE. `verdict` is the EPISTEMIC conclusion. Two fields, two axes.

Collapsing them is what happened in natural-systems: `hypothesis:0009` needed a lifecycle word
("stop working on this"), `status` was the only field available, and `status: retired` SPENT it --
leaving the epistemic conclusion nowhere to live at all. The word it was spent on was false besides:
`retired` asserts abandonment, and the pre-registered decisive test had RUN and concluded. The author
ruled the true record `complete` + `refuted` (fb-2026-07-11-005).

☠️ Five drafts of the design instead read the non-significant confirmatory null (z = -0.889) and
inferred `weakened`. All five were wrong -- the verdict turns on what the test was FOR, which lives
in the pre-registration and not in the p-value -- and that is precisely why the migration REFUSES a
terminal status rather than mapping it. So read the fixtures below as fixtures: the cell this file
pins hardest, `retired` with NO verdict, is the one 0009 turned out NOT to be.

This file was `test_hypothesis_disposition.py`, and every test in it survives -- because the SUBJECT
was never `disposition`. The subject is that a hypothesis nobody is working on must stop topping the
attention ranking, WITHOUT that being inferred from the evidence. `disposition` was one mechanism for
saying so; it was authored on **zero of 147** hypotheses in the corpus, and the lifecycle now says it
in the field that was always meant to. The mechanism changed. The guarantees did not.

The round-trip test is still the one that matters. `Entity` is `extra="ignore"`, so a frontmatter key
that is not a declared model field is SILENTLY DROPPED at `model_validate`. That is exactly what
happened to `phase`: in the template, in the renderer's key set, absent from the model, and therefore
never reaching the graph. A field that does not survive author -> model -> graph does not exist,
however correct it looks in the template.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

if "conftest" in sys.modules and not hasattr(sys.modules["conftest"], "build_entity_graph"):
    del sys.modules["conftest"]
from conftest import build_entity_graph
from rdflib import Dataset, Literal, Namespace, URIRef

from science_tool.graph.sources import load_project_sources

PROJECT_NS = Namespace("http://example.org/project/")
SCI = Namespace("http://example.org/science/vocab/")


def _hypothesis(*, status: str = "active", **extra: object) -> dict:
    frontmatter: dict[str, object] = {
        "title": "H",
        "status": status,
        "related": [],
        "source_refs": [],
        "created": "2026-07-11",
        "updated": "2026-07-11",
    }
    frontmatter.update(extra)
    return {"kind": "hypothesis", "id": "0009-x", "frontmatter": frontmatter, "body": "Body."}


def _load_one(project_root: Path, entity_id: str):
    sources = load_project_sources(project_root)
    return next(e for e in sources.entities if e.id == entity_id)


def _pin_schema_2(project_root: Path) -> None:
    """DECLARE the project migrated -- which is the only way a project is migrated.

    `entity migrate-hypothesis` writes this pin as its final act, after every file is rewritten and
    re-validated. Every instrument that reads the lifecycle reads THIS, never the shape of the files:
    a project whose hypotheses merely *look* migrated has declared nothing.
    """
    import yaml

    path = project_root / "science.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["entity_schema_version"] = 2
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def test_BOTH_axes_round_trip_from_frontmatter_to_graph(tmp_path: Path) -> None:
    """Author -> Entity -> graph. Every hop, for BOTH fields.

    A field that is not declared on the model is dropped at `model_validate` and the graph never sees
    it -- which would make every downstream consumer (attention ranking is GRAPH-based) unable to act
    on it. This is `phase`'s bug, and this is its guard, now pointed at the fields that replaced it.
    """
    graph_path = build_entity_graph(
        tmp_path,
        [_hypothesis(status="complete", verdict="refuted", closure_basis="pre-registration:0004-t078")],
    )

    entity = _load_one(tmp_path, "hypothesis:0009-x")
    assert entity.status == "complete"  # survived model_validate...
    assert entity.verdict == "refuted"  # ...and so did the OTHER axis
    assert entity.closure_basis == "pre-registration:0004-t078"

    ds = Dataset()
    ds.parse(source=str(graph_path), format="trig")
    knowledge = ds.graph(URIRef(PROJECT_NS["graph/knowledge"]))
    uri = URIRef(PROJECT_NS["hypothesis/0009-x"])

    assert (uri, SCI.projectStatus, Literal("complete")) in knowledge
    assert (uri, SCI.verdict, Literal("refuted")) in knowledge, (
        "the verdict did not reach the graph -- no consumer could ever act on it"
    )
    # And the field they replaced is GONE from the graph, not merely unused.
    assert not list(knowledge.triples((None, SCI.disposition, None)))


def test_closure_is_NEVER_inferred_from_the_verdict(tmp_path: Path) -> None:
    """A REFUTED hypothesis that nobody has closed is still OPEN — and still live work.

    Inferring closure from the verdict re-collapses the two axes. "Refuted and still being worked" is
    a legitimate, common state: you are writing it up, or probing why it failed. The system must not
    decide you are done with a claim because the evidence went against it.
    """
    from science_tool.entities import CLOSED_LIFECYCLE_STATUSES

    build_entity_graph(tmp_path, [_hypothesis(status="active", verdict="refuted")])

    entity = _load_one(tmp_path, "hypothesis:0009-x")

    assert entity.status == "active"
    assert entity.verdict == "refuted"
    assert entity.status not in CLOSED_LIFECYCLE_STATUSES  # the evidence spoke; nobody closed it


@pytest.mark.parametrize(
    ("status", "verdict"),
    [
        ("active", "refuted"),  # disproved, still being written up
        ("complete", "supported"),  # confirmed and done
        ("retired", None),  # closed for PRAGMATIC reasons -- epistemically UNDECIDED
        ("complete", "refuted"),  # disproved and closed
        ("superseded", "supported"),  # formerly supported, now REPLACED
    ],
)
def test_status_and_verdict_are_independent(tmp_path: Path, status: str, verdict: str | None) -> None:
    """Every cell is legal, and two of them are why one field could never carry both.

    `retired` + no verdict is the cell the collapse DESTROYED: closed for pragmatic reasons,
    epistemically undecided. There was no way to say it, so natural-systems said `refuted` instead.

    `superseded` + `supported` is the other: a claim that was supported and has now been replaced.
    Writing `superseded` into the collapsed field OVERWROTE `supported` and destroyed the conclusion.
    """
    extra: dict[str, object] = {}
    if verdict is not None:
        extra["verdict"] = verdict
    if status in {"retired", "archived"}:
        extra["closure_basis"] = "authored: funding ended"

    build_entity_graph(tmp_path, [_hypothesis(status=status, **extra)])

    entity = _load_one(tmp_path, "hypothesis:0009-x")

    assert entity.status == status
    assert entity.verdict == verdict


# NOTE: "a terminal status requires a basis" (`complete` -> verdict, `retired` -> closure_basis,
# `superseded` -> lineage or basis) is a SCHEMA invariant, and it is asserted where it lives:
# `model/tests/test_mixin_hypothesis.py`. It is deliberately NOT re-asserted as a model_validator --
# that would rebuild the second authority D3 abolishes, and the two would drift.


def _terminal_hypothesis_with_open_questions(tmp_path: Path, n: int) -> Path:
    """A CLOSED hypothesis with `n` debt-status questions related to it.

    `complete` + `refuted` is natural-systems' `hypothesis:0009` in its migrated form: the evidence
    went against it (verdict) and the work is finished (lifecycle). Both facts, in their own fields.
    """
    entities = [
        _hypothesis(
            status="complete",
            verdict="refuted",
            closure_basis="pre-registration:0004-t078",
            related=[f"question:{i:04d}-q" for i in range(n)],
        )
    ]
    for i in range(n):
        entities.append(
            {
                "kind": "question",
                "id": f"{i:04d}-q",
                "frontmatter": {
                    "title": f"Q{i}",
                    "status": "active",  # a DEBT status
                    "related": ["hypothesis:0009-x"],
                    "source_refs": [],
                    "created": "2026-07-11",
                    "updated": "2026-07-11",
                },
                "body": "Body.",
            }
        )
    return build_entity_graph(tmp_path, entities)


def test_terminal_hypothesis_stays_queryable_and_provenance_visible(tmp_path: Path) -> None:
    """Closure is NOT hiding. The entity, both its axes, and its lineage stay in the graph."""
    graph_path = _terminal_hypothesis_with_open_questions(tmp_path, 3)

    ds = Dataset()
    ds.parse(source=str(graph_path), format="trig")
    knowledge = ds.graph(URIRef(PROJECT_NS["graph/knowledge"]))
    uri = URIRef(PROJECT_NS["hypothesis/0009-x"])

    assert (uri, SCI.projectStatus, Literal("complete")) in knowledge
    assert (uri, SCI.verdict, Literal("refuted")) in knowledge


def test_questions_on_a_terminal_hypothesis_become_rehoming_debt(tmp_path: Path) -> None:
    """Closing a hypothesis UNHOUSES its questions -- it does not answer them.

    If they vanished from attention alongside their hypothesis, closure would convert a visible debt
    into an invisible one, which is worse than the bug being fixed.
    """
    from science_tool.graph.attention import list_rehoming_debt

    graph_path = _terminal_hypothesis_with_open_questions(tmp_path, 3)
    _pin_schema_2(tmp_path)

    result = list_rehoming_debt(graph_path)

    assert result.status == "ok"
    assert len(result.rows) == 3
    assert {r["terminal_hypothesis"] for r in result.rows} == {"hypothesis:0009-x"}


def test_rehoming_debt_is_UNWIRED_over_a_project_that_has_not_MIGRATED(tmp_path: Path) -> None:
    """An UNMIGRATED hypothesis carries the verdict in `status`, so its closure is UNREADABLE.

    A zero here would not mean "no debt" -- it would mean "I cannot read this project". That is the
    silent-instrument bug, and this is the guard against re-introducing it via the migration itself.
    """
    from science_tool.graph.attention import list_rehoming_debt

    graph_path = build_entity_graph(tmp_path, [_hypothesis(status="refuted")])  # the OLD vocabulary

    result = list_rehoming_debt(graph_path)

    assert result.status == "unwired"
    assert result.code == "hypothesis_lifecycle_unmigrated"
    assert "entity_schema_version" in (result.reason or "")


def test_migration_is_read_from_the_PIN_and_never_from_the_STATUS_VALUES(tmp_path: Path) -> None:
    """☠️ The heuristic this test forbids would have called natural-systems MIGRATED.

    An earlier cut of the instrument decided "has this project migrated?" by checking whether its
    hypotheses' `status` values were lifecycle words. That inference fails on the exact project that
    opened this arc: natural-systems authored `status: retired` and `status: active` onto UNMIGRATED
    hypotheses -- both lifecycle words -- while `retired` there MEANT `refuted`. A shape heuristic
    reads that corpus as migrated, then reads `retired` as a closure. Confidently, and wrongly.

    So the project below looks migrated in every file and has declared nothing. It is unwired.
    """
    from science_tool.graph.attention import list_rehoming_debt

    graph_path = build_entity_graph(
        tmp_path,
        [
            # Every status here is a LIFECYCLE word. Not one of them is a declaration.
            _hypothesis(status="retired"),
            {
                "kind": "hypothesis",
                "id": "0010-y",
                "frontmatter": {
                    "title": "H2",
                    "status": "active",
                    "related": [],
                    "source_refs": [],
                    "created": "2026-07-11",
                    "updated": "2026-07-11",
                },
                "body": "Body.",
            },
        ],
    )

    result = list_rehoming_debt(graph_path)

    assert result.status == "unwired"
    assert result.code == "hypothesis_lifecycle_unmigrated"


def test_rehoming_debt_over_a_MIGRATED_project_with_nothing_closed_is_a_TRUE_zero(tmp_path: Path) -> None:
    """...and this is the other half, which the old instrument could not express.

    Under `disposition` an absent field meant "unreadable", so a project that had simply closed
    nothing reported `unwired` forever -- and NO project ever authored the field. Under the lifecycle,
    a project that has DECLARED itself migrated can be read, so "nothing is terminal" becomes a fact
    the instrument can establish. Zero means zero. An instrument that can never say zero is as
    useless as one that always does.
    """
    from science_tool.graph.attention import list_rehoming_debt

    graph_path = build_entity_graph(tmp_path, [_hypothesis(status="active")])
    _pin_schema_2(tmp_path)

    result = list_rehoming_debt(graph_path)

    # `empty`, NOT `unwired` -- and the whole value of `InstrumentResult` is that those are different
    # words. `empty` is a live instrument reporting a true zero; `unwired` is an instrument saying it
    # could not look. The old code could only ever say the second.
    assert result.status == "empty"
    assert result.rows == []


def test_terminal_hypothesis_is_not_an_attention_candidate() -> None:
    """The core defect: a hypothesis nobody was working on TOPPED the attention ranking.

    Every term in the weight is highest for a hypothesis that just died -- it accumulated the most
    incoming bears_on and the most open questions precisely BECAUSE it was the organizing frame.
    natural-systems' hypothesis:0009 led on open_question_debt=10 and 27 incoming bears_on, so being
    disproved made it MORE attention-worthy and the system recommended working hardest on the thing
    it believed least (fb-2026-07-11-005).

    Note what makes the two differ here: NOT the verdict, which is `refuted` on BOTH. The dead one is
    `complete` and the live one is `active`. Ranking is a question about work, and work is the
    lifecycle's axis -- so a refuted hypothesis somebody is still writing up stays in the ranking,
    exactly as it should.
    """
    from rdflib import Dataset as RDFDataset

    from science_tool.graph.attention import compute_attention_candidates
    from science_tool.graph.io import SCI_NS

    ds = RDFDataset()
    knowledge = ds.graph(URIRef(PROJECT_NS["graph/knowledge"]))

    dead = URIRef(PROJECT_NS["hypothesis/0009-dead"])
    live = URIRef(PROJECT_NS["hypothesis/0010-live"])
    for uri in (dead, live):
        knowledge.add((uri, SCI_NS.freshnessState, Literal("stale")))
        knowledge.add((uri, SCI_NS.verdict, Literal("refuted")))  # SAME verdict on both
    # The dead one is CLOSED and is also the better-connected, higher-debt entity -- i.e. exactly the
    # one the old ranking would have put first.
    knowledge.add((dead, SCI_NS.projectStatus, Literal("complete")))
    knowledge.add((live, SCI_NS.projectStatus, Literal("active")))
    for i in range(5):
        q = URIRef(PROJECT_NS[f"question/{i:04d}-q"])
        knowledge.add((q, SCI_NS.projectStatus, Literal("active")))
        knowledge.add((q, URIRef("http://www.w3.org/2004/02/skos/core#related"), dead))
        knowledge.add((q, SCI_NS.bearsOn, dead))

    result = compute_attention_candidates(ds, epsilon=0.05)

    assert result.status == "ok"
    ids = [c.entity_id for c in result.rows]
    assert "hypothesis:0009-dead" not in ids, "a terminal hypothesis is still being ranked"
    assert "hypothesis:0010-live" in ids, "closure must not drop live hypotheses"
