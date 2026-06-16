import pytest
from science_tool.annotation.promote import (
    Promotable, PromotionCorpus, decide_candidates, normalize_claim,
)


def _corpus(titles_to_slug=None, slugs=None, derived=None, ambiguous=None):
    return PromotionCorpus(
        title_to_ref={normalize_claim(t): s for t, s in (titles_to_slug or {}).items()},
        existing_slugs=set(slugs or []),
        derived_refs=set(derived or []),
        ambiguous_titles={normalize_claim(t) for t in (ambiguous or [])},
    )


def test_ambiguous_title_skips_not_links():
    # Corpus already holds two same-kind entities with the same normalized title.
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="Shared claim text", subject=None, object=None)
    corp = _corpus(titles_to_slug={"Shared claim text": "proposition:shared-claim-text"},
                   ambiguous=["Shared claim text"])
    [c] = decide_candidates([p], corp)
    assert c.decision == "SKIP" and c.reason == "promote-link-ambiguous"


def test_numeric_kind_never_collides():
    # slug_addressed=False: an occupied slug does NOT become a COLLISION (numeric reserves a number).
    p = Promotable(kind="question", ref="annotation:a#f1", frag="f1",
                   claim="Alpha beta", subject=None, object=None)
    corp = _corpus(slugs={"alpha-beta"})
    [c] = decide_candidates([p], corp, slug_addressed=False)
    assert c.decision == "MINT" and c.slug == "alpha-beta" and c.kind == "question"


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
        _statement_ann("a-5", "A hypothesis", status=Status.OPEN, atype="hypothesis"),
        _statement_ann("a-6", "A metaphor", status=Status.OPEN, atype="metaphor"),
        _statement_ann("a-4", "Dismissed claim", status=Status.DISMISSED),
    )
    sidecar = anno_io.Sidecar(annotations=anns)

    promotable, skipped = collect_promotable(sidecar, sidecar_path, tmp_path, derived_refs=set())
    # proposition + question + hypothesis are now all promotable, tagged with their kind.
    assert [(p.frag, p.kind) for p in promotable] == [
        ("a-1", "proposition"), ("a-3", "question"), ("a-5", "hypothesis"),
    ]
    assert skipped["promote-already-promoted"] == 1
    assert skipped["promote-non-promotable-type"] == 1   # the metaphor
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


def test_apply_mints_proposition_and_backlinks(tmp_path):
    from datetime import date
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import (
        apply_candidates, collect_promotable, decide_candidates, load_corpus,
    )
    from science_tool.annotation.query import read_sidecar_strict

    # project layout
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    paper_dir = tmp_path / "papers"
    paper_dir.mkdir()
    md = paper_dir / "smith2020.source.md"
    md.write_text("Cells divide rapidly.\n", encoding="utf-8")
    sidecar_path = anno_io.sidecar_for_markdown(md)
    ann = _statement_ann("a-1", "Cells divide rapidly", status=Status.OPEN, subject="Cells")
    anno_io.write_sidecar(sidecar_path, anno_io.Sidecar(annotations=(ann,)))

    corpus = load_corpus(tmp_path)
    promotable, _ = collect_promotable(read_sidecar_strict(sidecar_path), sidecar_path, tmp_path, derived_refs=corpus.derived_refs)
    candidates = decide_candidates(promotable, corpus)
    report = apply_candidates(
        candidates, sidecar_path=sidecar_path, project_root=tmp_path,
        paper_ref="paper:smith2020", as_of=date(2026, 6, 16),
    )

    assert report.minted == 1
    prop = (tmp_path / "entities" / "propositions" / "cells-divide-rapidly.md").read_text(encoding="utf-8")
    assert "## Claim\n\nCells divide rapidly" in prop
    assert "subject: Cells" in prop
    assert "annotation:papers/smith2020.source#a-1" in prop
    assert "paper:smith2020" in prop
    # backlink written into sidecar; status unchanged
    re_ann = read_sidecar_strict(sidecar_path).annotations[0]
    assert re_ann.promoted_to == "proposition:cells-divide-rapidly"
    assert re_ann.status == Status.OPEN


def test_apply_links_to_existing_appends_both_refs_preserves_prose(tmp_path):
    from datetime import date
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.query import read_sidecar_strict
    from science_tool.annotation.promote import (
        apply_candidates, collect_promotable, decide_candidates, load_corpus,
    )

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    existing = tmp_path / "entities" / "propositions" / "known-claim.md"
    existing.write_text(
        '---\nid: proposition:known-claim\ntype: proposition\ntitle: Known claim\n'
        'status: draft\nsource_refs:\n  - "paper:other"\n'
        'created: "2026-06-01"\nupdated: "2026-06-01"\n---\n'
        "# Known claim\n\n## Claim\n\nHand-authored prose.\n",
        encoding="utf-8",
    )
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Known claim.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    ann = _statement_ann("a-1", "Known claim", status=Status.OPEN)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=(ann,)))

    corpus = load_corpus(tmp_path)
    promotable, _ = collect_promotable(read_sidecar_strict(sp), sp, tmp_path, derived_refs=corpus.derived_refs)
    candidates = decide_candidates(promotable, corpus)
    assert candidates[0].decision == "LINK"

    report = apply_candidates(candidates, sidecar_path=sp, project_root=tmp_path,
                              paper_ref="paper:p", as_of=date(2026, 6, 16))
    assert report.linked == 1
    text = existing.read_text(encoding="utf-8")
    assert "Hand-authored prose." in text                 # prose preserved (no clobber)
    assert "annotation:papers/p.source#a-1" in text        # annotation ref appended
    assert "paper:p" in text and "paper:other" in text     # paper ref appended; original kept
    assert "2026-06-16" in text and "updated:" in text  # `updated` advanced (renderer quote-style agnostic)
    assert read_sidecar_strict(sp).annotations[0].promoted_to == "proposition:known-claim"


def test_apply_refuses_overwrite_of_different_claim(tmp_path):
    # An explicit-id MINT (e.g. from a curator override) must never clobber an unrelated proposition.
    import pytest
    from datetime import date
    from science_tool.annotation.promote import PromotionApplyError, PromotionCandidate, apply_candidates

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    existing = tmp_path / "entities" / "propositions" / "shared.md"
    existing.write_text(
        '---\nid: proposition:shared\ntype: proposition\ntitle: Totally different claim\n'
        'status: draft\ncreated: "2026-06-16"\nupdated: "2026-06-16"\n---\n# x\n',
        encoding="utf-8",
    )
    cand = PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="A brand new claim",
                              subject=None, object=None, decision="MINT", slug="shared",
                              reason="override explicit id")
    with pytest.raises(PromotionApplyError):
        apply_candidates([cand], sidecar_path=tmp_path / "x.anno.trig",
                         project_root=tmp_path, paper_ref="paper:p", as_of=date(2026, 6, 16))


def test_apply_is_idempotent(tmp_path):
    # Running the full flow twice mints once; the second run's queue is empty.
    from datetime import date
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import (
        apply_candidates, collect_promotable, decide_candidates, load_corpus,
    )
    from science_tool.annotation.query import read_sidecar_strict
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Claim text body.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    ann = _statement_ann("a-1", "Claim text body", status=Status.OPEN)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=(ann,)))

    def run():
        corpus = load_corpus(tmp_path)
        pr, _ = collect_promotable(read_sidecar_strict(sp), sp, tmp_path, derived_refs=corpus.derived_refs)
        return apply_candidates(decide_candidates(pr, corpus), sidecar_path=sp,
                                project_root=tmp_path, paper_ref="paper:p", as_of=date(2026, 6, 16))

    assert run().minted == 1
    second = run()
    assert second.minted == 0 and second.linked == 0


def test_override_flips_mint_to_link():
    from science_tool.annotation.promote import PromotionCandidate, apply_overrides

    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="C", subject=None, object=None,
                               decision="MINT", slug="c", reason="new proposition")]
    edited = [{"annotation": "annotation:a#f1", "decision": "LINK", "slug": "proposition:existing"}]
    [out] = apply_overrides(base, edited, existing_refs={"proposition:existing"})
    assert out.decision == "LINK" and out.slug == "proposition:existing"


def test_override_explicit_id_resolves_collision():
    from science_tool.annotation.promote import PromotionCandidate, apply_overrides

    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="C", subject=None, object=None,
                               decision="COLLISION", slug="c", reason="promote-slug-collision")]
    edited = [{"annotation": "annotation:a#f1", "decision": "MINT", "slug": "proposition:c-2"}]
    [out] = apply_overrides(base, edited, existing_refs=set())
    assert out.decision == "MINT" and out.slug == "c-2"


def test_override_unchanged_row_passthrough():
    from science_tool.annotation.promote import PromotionCandidate, apply_overrides

    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="C", subject=None, object=None,
                               decision="MINT", slug="c", reason="new")]
    [out] = apply_overrides(base, [{"annotation": "annotation:a#f1", "decision": "MINT", "slug": "c"}], existing_refs=set())
    assert out.decision == "MINT" and out.slug == "c"


def test_override_bad_link_target_fails_loud():
    import pytest
    from science_tool.annotation.promote import PromotionCandidate, PromotionOverrideError, apply_overrides

    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="C", subject=None, object=None,
                               decision="MINT", slug="c", reason="new")]
    with pytest.raises(PromotionOverrideError):
        apply_overrides(base, [{"annotation": "annotation:a#f1", "decision": "LINK", "slug": "proposition:missing"}], existing_refs=set())


def test_override_unknown_ref_fails_loud():
    import pytest
    from science_tool.annotation.promote import PromotionOverrideError, apply_overrides

    with pytest.raises(PromotionOverrideError):
        apply_overrides([], [{"annotation": "annotation:zzz#f9", "decision": "MINT", "slug": "x"}], existing_refs=set())


def test_override_untouched_collision_row_passes_through():
    # A fed-back file mixes one edited row with an untouched COLLISION row; the latter must
    # pass through (not raise) so apply_candidates can skip it.
    from science_tool.annotation.promote import PromotionCandidate, apply_overrides

    base = [
        PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="A", subject=None, object=None,
                           decision="COLLISION", slug="a", reason="promote-slug-collision"),
        PromotionCandidate(ref="annotation:a#f2", frag="f2", claim="B", subject=None, object=None,
                           decision="MINT", slug="b", reason="new"),
    ]
    edited = [
        {"annotation": "annotation:a#f1", "decision": "COLLISION", "slug": "a"},   # untouched
        {"annotation": "annotation:a#f2", "decision": "MINT", "slug": "proposition:b-2"},  # renamed
    ]
    out = apply_overrides(base, edited, existing_refs=set())
    assert out[0].decision == "COLLISION"
    assert out[1].decision == "MINT" and out[1].slug == "b-2"


def test_proposition_target_is_default_and_slug_addressed():
    from science_tool.annotation.promote import PROMOTABLE_KINDS, build_targets
    targets = build_targets()
    assert set(PROMOTABLE_KINDS) == {"proposition", "question", "hypothesis"}
    assert targets["proposition"].slug_addressed is True
    assert callable(targets["proposition"].mint)


def test_entity_dest_resolves_by_kind(tmp_path):
    from science_tool.annotation.promote import entity_dest
    # proposition (slug strategy) and question (numeric) resolve under their homes.
    assert entity_dest("proposition:foo-bar", tmp_path).name == "foo-bar.md"
    assert entity_dest("proposition:foo-bar", tmp_path).parent.name == "propositions"
    assert entity_dest("question:0007-foo", tmp_path).name == "0007-foo.md"
    assert entity_dest("question:0007-foo", tmp_path).parent.name == "questions"
