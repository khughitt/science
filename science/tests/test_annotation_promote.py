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
