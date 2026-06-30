import hashlib
import json as _json
from datetime import datetime, timezone
from pathlib import Path

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
    scan_literature_assertions,
)
from science_tool.annotation import io as anno_io
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
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


_CREATED = datetime(2026, 6, 30, tzinfo=timezone.utc)
_ANN_REF = "annotation:entities/papers/Smith2020.source#a-1"


def _ann(
    frag: str,
    *,
    stance: str,
    atype: str = "proposition",
    status: Status = Status.OPEN,
    promoted_to: str | None = "proposition:p",
) -> Annotation:
    body = _json.dumps({"section": "abstract", "stance": stance})
    non_open = status is not Status.OPEN
    return Annotation(
        id=frag,
        target=SpecificResource(
            source="x.source.md",
            selector=TextQuoteSelector(exact=frag, prefix="", suffix=""),
        ),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type=atype,
        source="llm-annot:m:paper-annotate-v1",
        status=status,
        creator="paper-annotate",
        created=_CREATED,
        content_hash="0" * 64,
        modified=_CREATED if non_open else None,
        modified_by="curator" if non_open else None,
        promoted_to=promoted_to,
    )


def _write_paper_sidecar(root: Path, citekey: str, anns: list[Annotation]) -> None:
    md = root / "entities" / "papers" / f"{citekey}.source.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("Body.\n", encoding="utf-8")
    anno_io.write_sidecar(anno_io.sidecar_for_markdown(md), anno_io.Sidecar(annotations=tuple(anns)))


def test_scan_happy_path_collects_active_proposition_assertions(tmp_path: Path):
    _write_paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", stance="asserted")])
    refs = {"proposition:p": frozenset({"paper:Smith2020", _ANN_REF})}

    assertions, faults = scan_literature_assertions(tmp_path, refs)

    assert faults == []
    assert len(assertions) == 1
    a = assertions[0]
    assert (a.proposition_ref, a.paper_ref, a.stance) == (
        "proposition:p",
        "paper:Smith2020",
        "asserted",
    )


def test_scan_skips_question_and_hypothesis_typed_annotations(tmp_path: Path):
    _write_paper_sidecar(
        tmp_path,
        "Smith2020",
        [
            _ann("q-1", stance="asserted", atype="question", promoted_to="question:q"),
            _ann("h-1", stance="asserted", atype="hypothesis", promoted_to="hypothesis:h"),
        ],
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}

    assertions, faults = scan_literature_assertions(tmp_path, refs)

    assert assertions == []
    assert faults == []


def test_scan_skips_inactive_and_open_stance(tmp_path: Path):
    _write_paper_sidecar(
        tmp_path,
        "Smith2020",
        [
            _ann("f-1", stance="asserted", status=Status.FIXED),
            _ann("o-1", stance="open"),
            _ann("u-1", stance="asserted", promoted_to=None),
        ],
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}

    assertions, faults = scan_literature_assertions(tmp_path, refs)

    assert assertions == []
    assert faults == []


def test_scan_faults_on_non_proposition_target_for_proposition_typed(tmp_path: Path):
    _write_paper_sidecar(
        tmp_path,
        "Smith2020",
        [_ann("a-1", stance="asserted", promoted_to="question:q")],
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}

    assertions, faults = scan_literature_assertions(tmp_path, refs)

    assert assertions == []
    assert [f.reason for f in faults] == ["non-proposition-target"]


def test_scan_faults_on_stale_proposition(tmp_path: Path):
    _write_paper_sidecar(
        tmp_path,
        "Smith2020",
        [_ann("a-1", stance="asserted", promoted_to="proposition:gone")],
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}

    _, faults = scan_literature_assertions(tmp_path, refs)

    assert [f.reason for f in faults] == ["stale-proposition"]


def test_scan_faults_on_invalid_stance(tmp_path: Path):
    _write_paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", stance="maybe")])
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}

    _, faults = scan_literature_assertions(tmp_path, refs)

    assert [f.reason for f in faults] == ["invalid-stance"]


def test_scan_faults_on_malformed_json_body_without_raising(tmp_path: Path):
    ann = _ann("a-1", stance="asserted")
    bad_ann = Annotation(
        id=ann.id,
        target=ann.target,
        bodies=(TextualBody(value="{", format="application/json"),),
        motivation=ann.motivation,
        annotation_type=ann.annotation_type,
        source=ann.source,
        status=ann.status,
        creator=ann.creator,
        created=ann.created,
        content_hash=ann.content_hash,
        promoted_to=ann.promoted_to,
    )
    _write_paper_sidecar(tmp_path, "Smith2020", [bad_ann])
    refs = {"proposition:p": frozenset({"paper:Smith2020", _ANN_REF})}

    assertions, faults = scan_literature_assertions(tmp_path, refs)

    assert assertions == []
    assert [f.reason for f in faults] == ["invalid-stance"]


def test_scan_inactive_with_corrupt_target_is_skipped_not_errored(tmp_path: Path):
    _write_paper_sidecar(
        tmp_path,
        "Smith2020",
        [_ann("a-1", stance="asserted", status=Status.DISMISSED, promoted_to="question:q")],
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}

    assertions, faults = scan_literature_assertions(tmp_path, refs)

    assert assertions == []
    assert faults == []


def test_scan_faults_on_ownership_mismatch_paper_absent(tmp_path: Path):
    _write_paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", stance="asserted")])
    refs = {"proposition:p": frozenset({"paper:Other2019", _ANN_REF})}

    assertions, faults = scan_literature_assertions(tmp_path, refs)

    assert assertions == []
    assert [f.reason for f in faults] == ["ownership-mismatch"]


def test_scan_faults_on_ownership_mismatch_annotation_absent(tmp_path: Path):
    _write_paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", stance="asserted")])
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}

    assertions, faults = scan_literature_assertions(tmp_path, refs)

    assert assertions == []
    assert [f.reason for f in faults] == ["ownership-mismatch"]


def test_scan_accumulates_multiple_faults(tmp_path: Path):
    _write_paper_sidecar(
        tmp_path,
        "Smith2020",
        [
            _ann("a-1", stance="maybe"),
            _ann("a-2", stance="asserted", promoted_to="proposition:gone"),
        ],
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}

    _, faults = scan_literature_assertions(tmp_path, refs)

    assert {f.reason for f in faults} == {"invalid-stance", "stale-proposition"}
    assert len(faults) == 2
