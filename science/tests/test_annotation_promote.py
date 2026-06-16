import pytest
from science_tool.annotation.promote import (
    Promotable, PromotionCorpus, decide_candidates, normalize_claim,
)


def _corpus(titles_to_slug=None, slugs=None, derived=None):
    return PromotionCorpus(
        title_to_ref={normalize_claim(t): s for t, s in (titles_to_slug or {}).items()},
        existing_slugs=set(slugs or []),
        derived_refs=set(derived or []),
    )


def test_normalize_claim_casefolds_and_collapses():
    assert normalize_claim("The  CAT  sat") == normalize_claim("the cat sat") == "the cat sat"


def test_statement_extract_normalize_text_unchanged():
    # Guard: promotion must NOT casefold the Phase-3 match_text normalizer.
    from science_tool.annotation.statement_extract import _normalize_text
    assert _normalize_text("The Cat") == "The Cat"  # whitespace-only, case-preserving


def test_novel_claim_mints():
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="Novel claim here", subject=None, object=None)
    [c] = decide_candidates([p], _corpus())
    assert c.decision == "MINT" and c.slug == "novel-claim-here"


def test_identical_title_links():
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="Shared claim text", subject=None, object=None)
    corp = _corpus(titles_to_slug={"Shared claim text": "proposition:shared-claim-text"})
    [c] = decide_candidates([p], corp)
    assert c.decision == "LINK" and c.slug == "proposition:shared-claim-text"


def test_case_difference_still_links():
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="SHARED claim TEXT", subject=None, object=None)
    corp = _corpus(titles_to_slug={"shared claim text": "proposition:shared-claim-text"})
    [c] = decide_candidates([p], corp)
    assert c.decision == "LINK"


def test_slug_collision_against_corpus():
    # An existing slug occupied by a DIFFERENT-title proposition → COLLISION, not LINK.
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="Alpha beta", subject=None, object=None)
    corp = _corpus(slugs={"alpha-beta"})
    [c] = decide_candidates([p], corp)
    assert c.decision == "COLLISION"


def test_intra_batch_collision():
    # Two different claims truncating to the same slug in one batch → both COLLISION
    # (simulate with two claims that normalize_to_slug to the same value).
    a = Promotable(ref="annotation:a#f1", frag="f1", claim="Same Slug Here", subject=None, object=None)
    b = Promotable(ref="annotation:a#f2", frag="f2", claim="same slug here!!", subject=None, object=None)
    out = decide_candidates([a, b], _corpus())
    assert [c.decision for c in out] == ["MINT", "COLLISION"]


def test_unsluggable_claim_skipped():
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="…", subject=None, object=None)
    [c] = decide_candidates([p], _corpus())
    assert c.decision == "SKIP" and c.reason == "promote-claim-unsluggable"


def _statement_ann(frag, exact, *, status, atype="proposition", subject=None, promoted_to=None):
    import json as _json
    from datetime import datetime, timezone
    from science_tool.annotation.model import (
        Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody,
    )
    body = {"section": "abstract", "stance": "asserted"}
    if subject is not None:
        body["subject"] = subject
    created = datetime(2026, 6, 16, tzinfo=timezone.utc)
    non_open = status is not Status.OPEN  # the model requires modified/modified_by when not OPEN
    return Annotation(
        id=frag,
        target=SpecificResource(source="paper.md", selector=TextQuoteSelector(exact=exact, prefix="", suffix="")),
        bodies=(TextualBody(value=_json.dumps(body), format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type=atype,
        source="llm-annot:m:paper-annotate-v1", status=status,
        creator="paper-annotate", created=created,
        content_hash="0" * 64,  # llm-annot: sources require a content_hash (model __post_init__)
        modified=created if non_open else None,
        modified_by="curator" if non_open else None,
        promoted_to=promoted_to,
    )


def test_promotable_filters_queue(tmp_path):
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import collect_promotable

    md = tmp_path / "paper.md"
    md.write_text("x\n", encoding="utf-8")
    sidecar_path = anno_io.sidecar_for_markdown(md)
    anns = (
        _statement_ann("a-1", "Open proposition claim", status=Status.OPEN, subject="cells"),
        _statement_ann("a-2", "Already promoted", status=Status.OPEN, promoted_to="proposition:x"),
        _statement_ann("a-3", "A question", status=Status.OPEN, atype="question"),
        _statement_ann("a-4", "Dismissed claim", status=Status.DISMISSED),
    )
    sidecar = anno_io.Sidecar(annotations=anns)

    promotable, skipped = collect_promotable(sidecar, sidecar_path, tmp_path, derived_refs=set())
    assert [p.frag for p in promotable] == ["a-1"]
    assert promotable[0].subject == "cells"
    assert skipped["promote-already-promoted"] == 1
    assert skipped["promote-not-proposition-type"] == 1
    assert skipped["promote-inactive-status"] == 1


def test_malformed_statement_body_hard_fails(tmp_path):
    from datetime import datetime, timezone
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import (
        Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody,
    )
    from science_tool.annotation.promote import PromotionReadError, collect_promotable

    md = tmp_path / "paper.md"
    md.write_text("x\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    bad = Annotation(
        id="a-1",
        target=SpecificResource(source="paper.md", selector=TextQuoteSelector(exact="x", prefix="", suffix="")),
        bodies=(TextualBody(value="{ not json", format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        content_hash="0" * 64,  # required for llm-annot: source
    )
    with pytest.raises(PromotionReadError):
        collect_promotable(anno_io.Sidecar(annotations=(bad,)), sp, tmp_path, derived_refs=set())
