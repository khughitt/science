import pytest

from science_tool.annotation.promote import (
    Promotable,
    PromotionCandidate,
    PromotionCorpus,
    PromotionOverrideError,
    decide_candidates,
    normalize_claim,
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


def test_load_corpora_indexes_each_kind(tmp_path):
    from science_tool.annotation.promote import PROMOTABLE_KINDS, load_corpora

    # Two questions sharing a normalized title -> ambiguous; one hypothesis; one proposition.
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "hypotheses").mkdir(parents=True)
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    q1 = "---\nid: \"question:0001-dup\"\nkind: question\ntitle: \"Same question\"\nstatus: active\n---\n# Same question\n"
    q2 = "---\nid: \"question:0002-dup\"\nkind: question\ntitle: \"same QUESTION\"\nstatus: active\n---\n# same QUESTION\n"
    (tmp_path / "entities" / "questions" / "0001-dup.md").write_text(q1, encoding="utf-8")
    (tmp_path / "entities" / "questions" / "0002-dup.md").write_text(q2, encoding="utf-8")
    hyp = ("---\nid: \"hypothesis:0001-h\"\nkind: hypothesis\ntitle: \"A hypothesis\"\nstatus: proposed\n"
           "source_refs: [\"annotation:papers/p#fx\"]\n---\n# A hypothesis\n")
    (tmp_path / "entities" / "hypotheses" / "0001-h.md").write_text(hyp, encoding="utf-8")
    prop = "---\nid: \"proposition:a-claim\"\nkind: proposition\ntitle: \"A claim\"\nstatus: draft\n---\n# A claim\n"
    (tmp_path / "entities" / "propositions" / "a-claim.md").write_text(prop, encoding="utf-8")

    corpora, derived = load_corpora(tmp_path)
    assert set(corpora) == set(PROMOTABLE_KINDS)
    assert normalize_claim("Same question") in corpora["question"].ambiguous_titles
    assert corpora["hypothesis"].title_to_ref[normalize_claim("A hypothesis")] == "hypothesis:0001-h"
    assert "0001-h" in corpora["hypothesis"].existing_slugs
    # derived_refs are global (annotation ref from the hypothesis is visible kind-independently).
    assert "annotation:papers/p#fx" in derived
    assert "annotation:papers/p#fx" in corpora["question"].derived_refs


def _statement_ann(frag, exact, *, status, atype="proposition", subject=None, promoted_to=None):
    import json as _json
    from datetime import datetime, timezone

    from science_tool.annotation.model import (
        Annotation,
        Motivation,
        SpecificResource,
        Status,
        TextQuoteSelector,
        TextualBody,
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


def _promotion_project(tmp_path, *, existing: dict[str, str] | None = None):
    """Create a promotion project with a paper sidecar and optional propositions."""
    from science_tool.annotation import io as anno_io

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    for slug, title in (existing or {}).items():
        (tmp_path / "entities" / "propositions" / f"{slug}.md").write_text(
            f"---\nid: proposition:{slug}\nkind: proposition\ntitle: {title}\n"
            f"status: draft\nsource_refs:\n  - \"paper:other\"\n"
            f'created: "2026-06-01"\nupdated: "2026-06-01"\n---\n'
            f"# {title}\n\n## Claim\n\nHand-authored prose.\n",
            encoding="utf-8",
        )
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Body.\n", encoding="utf-8")
    return tmp_path, anno_io.sidecar_for_markdown(md)


def _link_candidate(slug, frag, ref=None):
    return PromotionCandidate(
        ref=ref or f"annotation:papers/p.source#{frag}",
        frag=frag,
        claim="Some claim",
        subject="s",
        object="o",
        decision="LINK",
        slug=slug,
        reason="existing entity",
        kind=slug.split(":", 1)[0],
    )


def _mint_candidate(kind, slug, frag, claim="Some claim"):
    return PromotionCandidate(
        ref=f"annotation:papers/p.source#{frag}",
        frag=frag,
        claim=claim,
        subject="s",
        object="o",
        decision="MINT",
        slug=slug,
        reason="new entity",
        kind=kind,
    )


def _refusing_source_refs_renderer(*_a, entity_path, **_k):
    from science_tool.entities import EntityDegradationError

    raise EntityDegradationError(f"{entity_path} would be degraded")


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
        Annotation,
        Motivation,
        SpecificResource,
        Status,
        TextQuoteSelector,
        TextualBody,
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
        apply_candidates,
        collect_promotable,
        decide_candidates,
        load_corpora,
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

    corpora, derived = load_corpora(tmp_path)
    promotable, _ = collect_promotable(read_sidecar_strict(sidecar_path), sidecar_path, tmp_path, derived_refs=derived)
    candidates = decide_candidates(promotable, corpora["proposition"])
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
    from science_tool.annotation.promote import (
        apply_candidates,
        collect_promotable,
        decide_candidates,
        load_corpora,
    )
    from science_tool.annotation.query import read_sidecar_strict

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    existing = tmp_path / "entities" / "propositions" / "known-claim.md"
    existing.write_text(
        '---\nid: proposition:known-claim\nkind: proposition\ntitle: Known claim\n'
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

    corpora, derived = load_corpora(tmp_path)
    promotable, _ = collect_promotable(read_sidecar_strict(sp), sp, tmp_path, derived_refs=derived)
    candidates = decide_candidates(promotable, corpora["proposition"])
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


def test_apply_candidates_translates_a_degradation_refusal(tmp_path, monkeypatch):
    """A renderer refusal must reach the promotion CLI as PromotionApplyError."""
    from datetime import date

    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import (
        PromotionApplyError,
        apply_candidates,
        collect_promotable,
        decide_candidates,
        load_corpora,
    )
    from science_tool.annotation.query import read_sidecar_strict
    from science_tool.entities import EntityDegradationError

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    existing = tmp_path / "entities" / "propositions" / "known-claim.md"
    existing.write_text(
        '---\nid: proposition:known-claim\nkind: proposition\ntitle: Known claim\n'
        'status: draft\nsource_refs:\n  - "paper:other"\n'
        'created: "2026-06-01"\nupdated: "2026-06-01"\n---\n'
        "# Known claim\n\n## Claim\n\nHand-authored prose.\n",
        encoding="utf-8",
    )
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Known claim.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=(
        _statement_ann("a-1", "Known claim", status=Status.OPEN),
    )))

    def refuse(current_text, refs_to_append, *, entity_path, as_of=None):
        raise EntityDegradationError(f"{entity_path} would be degraded")

    monkeypatch.setattr(promote_mod, "render_entity_source_refs", refuse)

    corpora, derived = load_corpora(tmp_path)
    promotable, _ = collect_promotable(read_sidecar_strict(sp), sp, tmp_path, derived_refs=derived)
    candidates = decide_candidates(promotable, corpora["proposition"])
    assert candidates[0].decision == "LINK"

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            candidates,
            sidecar_path=sp,
            project_root=tmp_path,
            paper_ref="paper:p",
            as_of=date(2026, 6, 16),
        )

    assert "known-claim" in str(excinfo.value)


def test_apply_candidates_aggregates_every_candidate_local_refusal(tmp_path, monkeypatch):
    """Two refused records prove planning continues beyond the first refusal."""
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import PromotionApplyError, apply_candidates

    root, sp = _promotion_project(
        tmp_path, existing={"bad-a": "Bad a", "bad-b": "Bad b", "good": "Good"}
    )
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))
    good = root / "entities" / "propositions" / "good.md"
    good_before = good.read_text(encoding="utf-8")
    real_renderer = promote_mod.render_entity_source_refs

    def refuse_the_bad_ones(current_text, refs, *, entity_path, as_of=None):
        if entity_path.name in ("bad-a.md", "bad-b.md"):
            return _refusing_source_refs_renderer(entity_path=entity_path)
        return real_renderer(current_text, refs, entity_path=entity_path, as_of=as_of)

    monkeypatch.setattr(promote_mod, "render_entity_source_refs", refuse_the_bad_ones)

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [
                _link_candidate("proposition:bad-a", "a-1"),
                _link_candidate("proposition:bad-b", "a-2"),
                _link_candidate("proposition:good", "a-3"),
            ],
            sidecar_path=sp,
            project_root=root,
            paper_ref="paper:p",
        )

    message = str(excinfo.value)
    assert "bad-a" in message
    assert "bad-b" in message
    assert good.read_text(encoding="utf-8") == good_before


def test_apply_candidates_aggregates_across_kinds_of_failure(tmp_path, monkeypatch):
    """Degradation, naming, and target failures share one candidate-local report."""
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import PromotionApplyError, apply_candidates

    root, sp = _promotion_project(tmp_path, existing={"bad": "Bad"})
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))
    real_renderer = promote_mod.render_entity_source_refs

    def refuse_only_bad(current_text, refs, *, entity_path, as_of=None):
        if entity_path.name == "bad.md":
            return _refusing_source_refs_renderer(entity_path=entity_path)
        return real_renderer(current_text, refs, entity_path=entity_path, as_of=as_of)

    monkeypatch.setattr(promote_mod, "render_entity_source_refs", refuse_only_bad)

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [
                _link_candidate("proposition:bad", "a-1"),
                _mint_candidate("question", "Not A Slug!", "a-2"),
                _link_candidate("proposition:missing", "a-3"),
            ],
            sidecar_path=sp,
            project_root=root,
            paper_ref="paper:p",
        )

    message = str(excinfo.value)
    assert "bad" in message
    assert "Not A Slug!" in message
    assert "missing" in message


def test_two_links_to_one_record_compose(tmp_path):
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import apply_candidates

    root, sp = _promotion_project(tmp_path, existing={"shared": "Shared"})
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))
    dest = root / "entities" / "propositions" / "shared.md"

    apply_candidates(
        [
            _link_candidate("proposition:shared", "a-1", ref="annotation:papers/p.source#a-1"),
            _link_candidate("proposition:shared", "a-2", ref="annotation:papers/p.source#a-2"),
        ],
        sidecar_path=sp,
        project_root=root,
        paper_ref="paper:p",
    )

    written = dest.read_text(encoding="utf-8")
    assert "annotation:papers/p.source#a-1" in written
    assert "annotation:papers/p.source#a-2" in written


def test_a_refused_batch_leaves_the_sidecar_unchanged(tmp_path, monkeypatch):
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import PromotionApplyError, apply_candidates

    root, sp = _promotion_project(tmp_path, existing={"bad": "Bad"})
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))
    sidecar_before = sp.read_text(encoding="utf-8")
    monkeypatch.setattr(promote_mod, "render_entity_source_refs", _refusing_source_refs_renderer)

    with pytest.raises(PromotionApplyError):
        apply_candidates(
            [_link_candidate("proposition:bad", "a-1")],
            sidecar_path=sp,
            project_root=root,
            paper_ref="paper:p",
        )

    assert sp.read_text(encoding="utf-8") == sidecar_before


def test_sidecar_drift_between_planning_and_apply_refuses(tmp_path, monkeypatch):
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import PromotionApplyError, apply_candidates

    root, sp = _promotion_project(tmp_path, existing={"known-claim": "Known claim"})
    anno_io.write_sidecar(
        sp,
        anno_io.Sidecar(
            annotations=(_statement_ann("a-1", "Known claim", status=Status.OPEN),)
        ),
    )
    real_publish = promote_mod.publish_edit

    def drift_the_sidecar_first(edit, *, project_root):
        if edit.path == sp:
            sp.write_text("{}\n", encoding="utf-8")
        return real_publish(edit, project_root=project_root)

    monkeypatch.setattr(promote_mod, "publish_edit", drift_the_sidecar_first)

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [_link_candidate("proposition:known-claim", "a-1")],
            sidecar_path=sp,
            project_root=root,
            paper_ref="paper:p",
        )

    assert "stage=write" in str(excinfo.value)
    assert sp.read_text(encoding="utf-8") == "{}\n"


def test_apply_refuses_overwrite_of_different_claim(tmp_path):
    # An explicit-id MINT (e.g. from a curator override) must never clobber an unrelated proposition.
    from datetime import date

    import pytest

    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import PromotionApplyError, PromotionCandidate, apply_candidates

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    existing = tmp_path / "entities" / "propositions" / "shared.md"
    existing.write_text(
        '---\nid: proposition:shared\nkind: proposition\ntitle: Totally different claim\n'
        'status: draft\ncreated: "2026-06-16"\nupdated: "2026-06-16"\n---\n# x\n',
        encoding="utf-8",
    )
    cand = PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="A brand new claim",
                              subject=None, object=None, decision="MINT", slug="shared",
                              reason="override explicit id")
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Body.\n", encoding="utf-8")
    sidecar_path = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sidecar_path, anno_io.Sidecar(annotations=()))
    with pytest.raises(PromotionApplyError):
        apply_candidates([cand], sidecar_path=sidecar_path,
                         project_root=tmp_path, paper_ref="paper:p", as_of=date(2026, 6, 16))


def test_apply_is_idempotent(tmp_path):
    # Running the full flow twice mints once; the second run's queue is empty.
    from datetime import date

    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import (
        apply_candidates,
        collect_promotable,
        decide_candidates,
        load_corpora,
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
        corpora, derived = load_corpora(tmp_path)
        pr, _ = collect_promotable(read_sidecar_strict(sp), sp, tmp_path, derived_refs=derived)
        return apply_candidates(decide_candidates(pr, corpora["proposition"]), sidecar_path=sp,
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
    assert callable(targets["proposition"].plan_mint)


def test_entity_dest_resolves_by_kind(tmp_path):
    from science_tool.annotation.promote import entity_dest
    # proposition (slug strategy) and question (numeric) resolve under their homes.
    assert entity_dest("proposition:foo-bar", tmp_path).name == "foo-bar.md"
    assert entity_dest("proposition:foo-bar", tmp_path).parent.name == "propositions"
    assert entity_dest("question:0007-foo", tmp_path).name == "0007-foo.md"
    assert entity_dest("question:0007-foo", tmp_path).parent.name == "questions"


def test_decide_all_preserves_order_and_kind_local_dedup():
    from science_tool.annotation.promote import build_targets, decide_all
    promotables = [
        Promotable(kind="question", ref="annotation:a#q", frag="q", claim="Shared text", subject=None, object=None),
        Promotable(kind="proposition", ref="annotation:a#p", frag="p", claim="Shared text", subject=None, object=None),
    ]
    corpora = {
        "question": _corpus(titles_to_slug={"Shared text": "question:0001-shared-text"}),
        "hypothesis": _corpus(),
        "proposition": _corpus(),  # proposition corpus does NOT contain "Shared text"
    }
    out = decide_all(promotables, corpora, build_targets())
    # order preserved; question LINKs (its corpus has the title), proposition MINTs (its does not)
    assert [c.frag for c in out] == ["q", "p"]
    assert out[0].decision == "LINK" and out[0].slug == "question:0001-shared-text"
    assert out[1].decision == "MINT" and out[1].kind == "proposition"


def test_override_link_must_be_same_kind():
    from science_tool.annotation.promote import apply_overrides
    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="Q text", subject=None,
                               object=None, decision="MINT", slug="q-text", reason="new entity",
                               kind="question")]
    rows = [{"annotation": "annotation:a#f1", "decision": "LINK", "slug": "proposition:q-text"}]
    with pytest.raises(PromotionOverrideError):
        apply_overrides(base, rows, existing_refs={"proposition:q-text", "question:0001-q-text"})


def test_override_numeric_mint_slug_strips_kind_prefix():
    from science_tool.annotation.promote import apply_overrides
    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="Q text", subject=None,
                               object=None, decision="MINT", slug="q-text", reason="new entity",
                               kind="question")]
    rows = [{"annotation": "annotation:a#f1", "decision": "MINT", "slug": "question:better-slug"}]
    [c] = apply_overrides(base, rows, existing_refs=set())
    assert c.decision == "MINT" and c.slug == "better-slug" and c.kind == "question"


def _q_mint_base():
    return [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="Q text", subject=None,
                               object=None, decision="MINT", slug="q-text", reason="new entity",
                               kind="question")]


def test_override_mint_wrong_kind_prefix_fails():
    from science_tool.annotation.promote import apply_overrides
    rows = [{"annotation": "annotation:a#f1", "decision": "MINT", "slug": "hypothesis:foo"}]
    with pytest.raises(PromotionOverrideError):
        apply_overrides(_q_mint_base(), rows, existing_refs=set())


def test_override_mint_invalid_slug_fails():
    # A slug that can't pass validate_slug must fail as a clean PromotionOverrideError,
    # not leak EntityCommandError from reserve_entity at apply time.
    from science_tool.annotation.promote import apply_overrides
    rows = [{"annotation": "annotation:a#f1", "decision": "MINT", "slug": "Not A Slug!"}]
    with pytest.raises(PromotionOverrideError):
        apply_overrides(_q_mint_base(), rows, existing_refs=set())
