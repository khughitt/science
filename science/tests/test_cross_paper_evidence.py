import hashlib

from rdflib import URIRef
from science_model.reasoning import (
    EvidenceRole,
    EvidenceStance,
    EvidenceStrength,
    EvidenceType,
    IndependenceTag,
)

from science_tool.annotation.cross_paper_evidence import (
    ACTIVE_STATUSES,
    AssertionFault,
    CrossPaperEvidenceError,
    DERIVED_STANCES,
    INDEPENDENT,
    KNOWN_STANCES,
    LITERATURE_TYPE,
    LiteratureAssertion,
    STANCE_EMIT,
    collapse_assertions,
    lit_assertion_uri,
)
from science_tool.graph.io import PROJECT_NS


def test_lit_assertion_uri_is_full_sha256_of_nul_joined_key():
    uri = lit_assertion_uri("proposition:p", "paper:Smith2020", "asserted")
    digest = hashlib.sha256(b"proposition:p\x00paper:Smith2020\x00asserted").hexdigest()
    assert uri == URIRef(PROJECT_NS[f"evidence-line/lit-assertion/{digest}"])
    assert len(digest) == 64


def test_lit_assertion_uri_is_deterministic_and_stance_sensitive():
    a = lit_assertion_uri("proposition:p", "paper:A", "asserted")
    b = lit_assertion_uri("proposition:p", "paper:A", "asserted")
    c = lit_assertion_uri("proposition:p", "paper:A", "negated")
    assert a == b
    assert a != c


def test_stance_emit_table_uses_real_enum_values():
    assert STANCE_EMIT["asserted"] == (
        EvidenceStance.SUPPORTS.value,
        EvidenceRole.PROXY_SUPPORT.value,
        EvidenceStrength.MODERATE.value,
    )
    assert STANCE_EMIT["negated"] == (
        EvidenceStance.DISPUTES.value,
        EvidenceRole.PROXY_SUPPORT.value,
        EvidenceStrength.MODERATE.value,
    )
    assert STANCE_EMIT["hypothesized"] == (
        EvidenceStance.SUPPORTS.value,
        EvidenceRole.BACKGROUND_CONSTRAINT.value,
        EvidenceStrength.WEAK.value,
    )
    assert set(STANCE_EMIT) == DERIVED_STANCES
    assert ACTIVE_STATUSES == frozenset({"open", "ack"})
    assert KNOWN_STANCES == DERIVED_STANCES | {"open"}
    assert LITERATURE_TYPE == EvidenceType.LITERATURE.value
    assert INDEPENDENT == IndependenceTag.INDEPENDENT.value


def test_collapse_dedupes_same_proposition_paper_stance_keeps_one():
    a1 = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-1", "A.anno.trig")
    a2 = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-2", "A.anno.trig")
    out = collapse_assertions([a1, a2])
    assert len(out) == 1
    assert out[0].proposition_ref == "proposition:p"


def test_collapse_keeps_both_stances_for_same_paper():
    sup = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-1", "A.anno.trig")
    dis = LiteratureAssertion("proposition:p", "paper:A", "negated", "ann-2", "A.anno.trig")
    out = collapse_assertions([sup, dis])
    keys = {(x.paper_ref, x.stance) for x in out}
    assert keys == {("paper:A", "asserted"), ("paper:A", "negated")}


def test_collapse_is_order_independent_and_deterministic():
    a1 = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-9", "A.anno.trig")
    a2 = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-1", "A.anno.trig")
    assert collapse_assertions([a1, a2]) == collapse_assertions([a2, a1])
    assert collapse_assertions([a1, a2])[0].annotation_id == "ann-1"


def test_collapse_uses_sidecar_as_final_deterministic_tiebreaker():
    a1 = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-1", "B.anno.trig")
    a2 = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-1", "A.anno.trig")
    assert collapse_assertions([a1, a2]) == collapse_assertions([a2, a1])
    assert collapse_assertions([a1, a2])[0].sidecar == "A.anno.trig"


def test_cross_paper_evidence_error_lists_all_faults():
    faults = (
        AssertionFault("A.anno.trig", "ann-1", "stale-proposition", "proposition:x missing"),
        AssertionFault("B.anno.trig", "ann-2", "invalid-stance", "stance 'maybe'"),
    )
    err = CrossPaperEvidenceError(faults)
    assert err.faults == faults
    text = str(err)
    assert "stale-proposition" in text and "invalid-stance" in text
    assert "ann-1" in text and "ann-2" in text
    assert "A.anno.trig" in text and "B.anno.trig" in text
    assert "proposition:x missing" in text and "stance 'maybe'" in text
