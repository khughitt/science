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


from science_tool.annotation.synthesize import build_scaffold, relation_hints


def _rel(frag, exact, *, predicate, subj, obj):
    body = (
        '{"object":"%s","predicate":"%s","predicate_source":"biored",'
        '"subject":"%s"}' % (obj, predicate, subj)
    )
    return _ann(frag, "relation", exact, body=body)


def test_relation_hints_overlap_and_unresolved_count():
    file_text = "alpha BRCA1 affects genomic instability omega"
    stmt = _ann("s1", "proposition", "BRCA1 affects genomic instability",
                body='{"section":"results","stance":"asserted"}',
                promoted_to="proposition:p")
    # overlapping relation (its exact lies inside the statement span)
    hit = _rel("r1", "BRCA1 affects", predicate="biolink:affects",
               subj="ncbigene:672", obj="GO:0006281")
    # relation whose exact is not in file_text → unresolved, counted, omitted
    miss = _rel("r2", "NOT PRESENT", predicate="biolink:regulates",
                subj="a", obj="b")
    hints, unresolved = relation_hints(file_text, [stmt], [hit, miss])
    assert unresolved == 1
    assert hints == [{
        "annotation_frag": "r1", "predicate": "biolink:affects",
        "subject": "ncbigene:672", "object": "GO:0006281",
    }]


def test_build_scaffold_shape():
    file_text = "BRCA1 affects genomic instability"
    stmt = _ann("s1", "proposition", "BRCA1 affects genomic instability",
                body='{"section":"results","stance":"asserted","subject":"BRCA1"}',
                promoted_to="proposition:brca1")
    sc = Sidecar(annotations=(stmt,))
    current = {"proposition:brca1": {"title": "BRCA1 claim", "subject": "BRCA1"}}
    scaffold, unresolved = build_scaffold(
        sc, file_text, current,
        ref_for=lambda frag: f"annotation:papers/p.source#{frag}",
    )
    assert scaffold["source"] == "llm-synth:<MODEL>:proposition-synthesize-v1"
    assert unresolved == 0
    [entry] = scaffold["propositions"]
    assert entry["proposition"] == "proposition:brca1"
    assert entry["title"] == "BRCA1 claim"
    assert entry["current"] == {"subject": "BRCA1", "object": None, "predicate": None,
                                "polarity": None, "claim_layer": None}
    assert entry["statements"][0]["annotation"] == "annotation:papers/p.source#s1"
    assert entry["relation_hints"] == []


import pytest
from science_tool.annotation.synthesize import (
    SynthesisCandidate, SynthesisReadError, parse_candidates_doc,
)

# in-scope set + per-proposition supporting-statement refs the parser validates against
SCOPE = {"proposition:p": {"annotation:papers/p.source#s1"}}
SRC = "llm-synth:claude-opus-4-8:proposition-synthesize-v1"


def _doc(candidates, source=SRC):
    return {"source": source, "candidates": candidates}


def test_parse_minimal_candidate():
    doc = _doc([{
        "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
        "predicate": "affects", "subject": "X", "object": "Y", "polarity": "positive",
        "claim_layer": "causal_effect",
    }])
    source, cands = parse_candidates_doc(doc, SCOPE)
    assert source == SRC
    assert cands == [SynthesisCandidate(
        proposition="proposition:p", annotation="annotation:papers/p.source#s1",
        fields={"predicate": "affects", "subject": "X", "object": "Y",
                "polarity": "positive", "claim_layer": "causal_effect"},
        override=frozenset(),
    )]


def test_bad_source_rejected():
    with pytest.raises(SynthesisReadError, match="source"):
        parse_candidates_doc(_doc([], source="llm-synth:<MODEL>:proposition-synthesize-v1"), SCOPE)


def test_duplicate_proposition_rejected():
    row = {"proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
           "claim_layer": "causal_effect"}
    with pytest.raises(SynthesisReadError, match="duplicate"):
        parse_candidates_doc(_doc([row, dict(row)]), SCOPE)


def test_explicit_null_field_rejected():
    with pytest.raises(SynthesisReadError, match="null|omit"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": None,
        }]), SCOPE)


def test_unknown_enum_value_rejected():
    with pytest.raises(SynthesisReadError, match="claim_layer"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "made_up",
        }]), SCOPE)


def test_out_of_scope_proposition_rejected():
    with pytest.raises(SynthesisReadError, match="in scope|scope"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:other", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "causal_effect",
        }]), SCOPE)


def test_annotation_not_supporting_rejected():
    with pytest.raises(SynthesisReadError, match="annotation"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#sX",
            "claim_layer": "causal_effect",
        }]), SCOPE)


def test_override_must_name_a_present_field():
    with pytest.raises(SynthesisReadError, match="override"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "causal_effect", "override": ["predicate"],
        }]), SCOPE)


def test_override_rejects_reasoning_source():
    with pytest.raises(SynthesisReadError, match="override"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "causal_effect", "override": ["reasoning_source"],
        }]), SCOPE)


from science_tool.annotation.synthesize import (
    SynthesisApplyError, SynthesisOverrideError, WritePlan, plan_writes, validate_candidate,
)


def _cand(fields, override=frozenset(), prop="proposition:p",
          ann="annotation:papers/p.source#s1"):
    return SynthesisCandidate(proposition=prop, annotation=ann, fields=fields, override=override)


def test_plan_writes_fill_only_unset():
    current = {"subject": "X"}                      # object/predicate/... unset
    cand = _cand({"subject": "X2", "object": "Y", "claim_layer": "causal_effect"})
    plan = plan_writes(current, cand)
    # subject already set & different & no override → blocked; object/claim_layer fill
    assert plan.writes == {"object": "Y", "claim_layer": "causal_effect"}
    assert plan.blocked == ("subject",)


def test_plan_writes_override_replaces():
    current = {"claim_layer": "empirical_regularity"}
    cand = _cand({"claim_layer": "causal_effect"}, override=frozenset({"claim_layer"}))
    plan = plan_writes(current, cand)
    assert plan.writes == {"claim_layer": "causal_effect"} and plan.blocked == ()


def test_plan_writes_signless_canonicalizes_polarity():
    current: dict = {}
    cand = _cand({"subject": "X", "object": "Y", "predicate": "binds"})   # sign-less
    plan = plan_writes(current, cand)
    assert plan.writes["polarity"] == "not_applicable"


def test_validate_predicate_requires_operands():
    current: dict = {}
    cand = _cand({"predicate": "affects", "subject": "X", "polarity": "positive"})  # no object
    with pytest.raises(SynthesisApplyError, match="subject and object|object"):
        validate_candidate(current, cand)


def test_validate_polarity_requires_predicate():
    current: dict = {}
    cand = _cand({"polarity": "positive"})         # bare polarity, no predicate
    with pytest.raises(SynthesisApplyError, match="predicate"):
        validate_candidate(current, cand)


def test_validate_sign_meaningful_missing_polarity_fails():
    current: dict = {}
    cand = _cand({"subject": "X", "object": "Y", "predicate": "affects"})  # needs signed polarity
    with pytest.raises(SynthesisApplyError):
        validate_candidate(current, cand)


def test_validate_override_of_unset_field_rejected():
    # override may only name a CURRENTLY-SET field; current={} ⇒ hard error (design §6/§7).
    cand = _cand({"claim_layer": "causal_effect"}, override=frozenset({"claim_layer"}))
    with pytest.raises(SynthesisOverrideError, match="override|unset"):
        validate_candidate({}, cand)


def test_validate_ok_returns_plan():
    current = {"subject": "X", "object": "Y"}
    cand = _cand({"predicate": "regulates", "polarity": "negative", "claim_layer": "causal_effect"})
    plan = validate_candidate(current, cand)
    assert plan.writes == {"predicate": "regulates", "polarity": "negative",
                           "claim_layer": "causal_effect"}
