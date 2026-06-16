from datetime import datetime, timezone

from science_tool.annotation.model import (
    Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody,
)
from science_tool.annotation.model import Sidecar
from science_tool.annotation.synthesize import in_scope_propositions, statement_context


def _ann(frag, atype, exact, *, body, promoted_to=None, status=Status.OPEN):
    return Annotation(
        id=frag,
        target=SpecificResource(source="p.source.md",
                                selector=TextQuoteSelector(exact=exact, prefix="", suffix="")),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type=atype,
        source="llm-annot:m:paper-annotate-v1", status=status,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        content_hash="0" * 64, promoted_to=promoted_to,
    )


def test_in_scope_groups_by_promoted_proposition():
    a = _ann("s1", "proposition", "X drives Y",
             body='{"section":"results","stance":"asserted","subject":"X","object":"Y"}',
             promoted_to="proposition:x-drives-y")
    b = _ann("s2", "proposition", "X drives Y too",
             body='{"section":"results","stance":"asserted"}',
             promoted_to="proposition:x-drives-y")
    q = _ann("q1", "question", "What about Z", body='{"section":"results","stance":"open"}',
             promoted_to="question:0001-z")          # not a proposition → excluded
    u = _ann("s3", "proposition", "Unpromoted",
             body='{"section":"results","stance":"asserted"}')   # promoted_to=None → excluded
    sc = Sidecar(annotations=(a, b, q, u))
    scope = in_scope_propositions(sc)
    assert set(scope) == {"proposition:x-drives-y"}
    assert [x.id for x in scope["proposition:x-drives-y"]] == ["s1", "s2"]


def test_statement_context_extracts_body_fields():
    a = _ann("s1", "proposition", "X drives Y",
             body='{"section":"results","stance":"asserted","subject":"X","object":"Y"}')
    ctx = statement_context(a, "annotation:papers/p.source#s1")
    assert ctx == {
        "annotation": "annotation:papers/p.source#s1",
        "exact": "X drives Y", "section": "results", "stance": "asserted",
        "subject": "X", "object": "Y",
    }
