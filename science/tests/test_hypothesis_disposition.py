"""`status` is the epistemic verdict. `disposition` is the workflow state.

They are ORTHOGONAL, and neither may be inferred from the other. Collapsing them is what
happened in natural-systems: `hypothesis:0009` needed a workflow word ("stop working on
this"), `status` was the only field available, and `status: retired` overwrote the epistemic
verdict -- recording a refutation that never happened. The hypothesis had failed to confirm
(a NON-significant confirmatory null, z = -0.889), which the vocabulary already called
`weakened` (fb-2026-07-11-005).

The round-trip test below is the one that matters. `Entity` is `extra="ignore"`, so a
frontmatter key that is not a declared model field is SILENTLY DROPPED at
`schema.model_validate(raw)`. That is exactly what happened to `phase`: it sits in the
template and in the renderer's key set, is absent from the model, and therefore NEVER
REACHES THE GRAPH. A field that does not survive author -> model -> graph does not exist,
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


def _hypothesis(*, status: str = "refuted", **extra: object) -> dict:
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


def test_disposition_round_trips_from_frontmatter_to_graph(tmp_path: Path) -> None:
    """Author -> Entity -> graph. Every hop.

    If `disposition` is not a declared model field it is dropped at model_validate and the
    graph never sees it -- which would make every downstream consumer (attention ranking is
    GRAPH-based) unable to act on it. This is `phase`'s bug, and this test is its guard.
    """
    graph_path = build_entity_graph(
        tmp_path,
        [_hypothesis(disposition="closed", disposition_basis="pre-registration:0004-t078")],
    )

    entity = _load_one(tmp_path, "hypothesis:0009-x")
    assert entity.disposition == "closed"  # survived model_validate
    assert entity.disposition_basis == "pre-registration:0004-t078"

    ds = Dataset()
    ds.parse(source=str(graph_path), format="trig")
    knowledge = ds.graph(URIRef(PROJECT_NS["graph/knowledge"]))
    uri = URIRef(PROJECT_NS["hypothesis/0009-x"])
    assert (uri, SCI.disposition, Literal("closed")) in knowledge, (
        "disposition did not reach the graph -- attention ranking could never act on it"
    )


def test_disposition_defaults_to_open_and_is_never_inferred_from_status(tmp_path: Path) -> None:
    """A REFUTED hypothesis with no authored disposition is OPEN.

    Inferring closure from a terminal epistemic status would re-collapse the two axes this
    field exists to separate, and would close hypotheses whose authors never said to.
    "Refuted and still being worked" is a legitimate, common state: you are writing it up,
    or probing why it failed.
    """
    build_entity_graph(tmp_path, [_hypothesis()])  # status: refuted, no disposition

    entity = _load_one(tmp_path, "hypothesis:0009-x")

    assert entity.disposition == "open"
    assert entity.disposition_basis is None


def test_closing_requires_a_basis(tmp_path: Path) -> None:
    """Closure is always an EXPLICIT authored act. `disposition: closed` must say what
    closed it -- otherwise retirement is an unexplained disappearance.

    The loader rejects it at load (ValueError wrapping the schema failure), so a hypothesis
    closed without a stated reason never reaches the graph at all.
    """
    with pytest.raises(ValueError, match="disposition_basis"):
        build_entity_graph(tmp_path, [_hypothesis(disposition="closed")])  # no basis


@pytest.mark.parametrize(
    ("status", "disposition"),
    [
        ("refuted", "open"),  # disproved, still being written up
        ("supported", "closed"),  # confirmed and done
        ("under-investigation", "closed"),  # closed for PRAGMATIC reasons -- epistemically undecided
        ("refuted", "closed"),  # disproved and closed
    ],
)
def test_status_and_disposition_are_independent(tmp_path: Path, status: str, disposition: str) -> None:
    """All four cells are legal.

    The third is the one `status: retired` CANNOT represent without lying: closed for
    pragmatic reasons, epistemically undecided. That is the case the collapse destroyed.
    """
    extra: dict[str, object] = {"disposition": disposition}
    if disposition == "closed":
        extra["disposition_basis"] = "authored: funding ended"
    build_entity_graph(tmp_path, [_hypothesis(status=status, **extra)])

    entity = _load_one(tmp_path, "hypothesis:0009-x")

    assert entity.status == status
    assert entity.disposition == disposition


def _closed_hypothesis_with_open_questions(tmp_path: Path, n: int) -> Path:
    """A CLOSED hypothesis with `n` debt-status questions related to it."""
    entities = [
        _hypothesis(
            status="refuted",
            disposition="closed",
            disposition_basis="pre-registration:0004-t078",
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
    """Closure is NOT hiding. The entity, its status, and its lineage stay in the graph."""
    graph_path = _closed_hypothesis_with_open_questions(tmp_path, 3)

    ds = Dataset()
    ds.parse(source=str(graph_path), format="trig")
    knowledge = ds.graph(URIRef(PROJECT_NS["graph/knowledge"]))
    uri = URIRef(PROJECT_NS["hypothesis/0009-x"])

    assert (uri, SCI.projectStatus, Literal("refuted")) in knowledge
    assert (uri, SCI.disposition, Literal("closed")) in knowledge


def test_questions_on_a_terminal_hypothesis_become_rehoming_debt(tmp_path: Path) -> None:
    """Closing a hypothesis UNHOUSES its questions -- it does not answer them.

    If they vanished from attention alongside their hypothesis, closure would convert a
    visible debt into an invisible one, which is worse than the bug being fixed.
    """
    from science_tool.graph.attention import list_rehoming_debt

    graph_path = _closed_hypothesis_with_open_questions(tmp_path, 3)

    result = list_rehoming_debt(graph_path)

    assert result.status == "ok"
    assert len(result.rows) == 3
    assert {r["terminal_hypothesis"] for r in result.rows} == {"hypothesis:0009-x"}


def test_rehoming_debt_is_unwired_when_nothing_declares_a_disposition(tmp_path: Path) -> None:
    """A project whose hypotheses predate the field has no CLOSED hypotheses -- but that is
    not the same as having no debt. Reporting a confident zero would be the silent-instrument
    bug: nothing has been closed because nothing CAN be closed."""
    from science_tool.graph.attention import list_rehoming_debt

    # build_entity_graph writes disposition only when authored; omit it entirely.
    graph_path = build_entity_graph(
        tmp_path, [{"kind": "question", "id": "0001-q", "frontmatter": {"title": "Q", "status": "active"}, "body": "B."}]
    )

    result = list_rehoming_debt(graph_path)

    assert result.status == "unwired"
    assert result.code == "no_disposition_declared"


def test_terminal_hypothesis_is_not_an_attention_candidate() -> None:
    """The core defect: a REFUTED hypothesis TOPPED the attention ranking.

    Every term in the weight is highest for a hypothesis that just died -- it accumulated
    the most incoming bears_on and the most open questions precisely BECAUSE it was the
    organizing frame. natural-systems' hypothesis:0009 led on open_question_debt=10 and 27
    incoming bears_on, so being disproved made it MORE attention-worthy and the system
    recommended working hardest on the thing it believed least (fb-2026-07-11-005).
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
        knowledge.add((uri, SCI_NS.projectStatus, Literal("refuted")))
    # The dead one is CLOSED and is also the better-connected, higher-debt entity --
    # i.e. exactly the one the old ranking would have put first.
    knowledge.add((dead, SCI_NS.disposition, Literal("closed")))
    knowledge.add((live, SCI_NS.disposition, Literal("open")))
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
