"""Phase 4a — statement→proposition promotion (decision + apply)."""

from __future__ import annotations

from dataclasses import dataclass

from science_tool.entities import EntityCommandError, slug_for_claim_text


def normalize_claim(text: str) -> str:
    """Promotion-specific normalizer: casefold + whitespace-collapse.

    DELIBERATELY separate from `statement_extract._normalize_text` (whitespace-only,
    case-preserving), which is baked into Phase-3 `match_text` and must not change.
    """
    return " ".join(text.casefold().split())


@dataclass(frozen=True)
class Promotable:
    ref: str            # "annotation:<relpath>#<frag>"
    frag: str           # annotation id within its sidecar
    claim: str          # the TextQuoteSelector exact span
    subject: str | None
    object: str | None


@dataclass(frozen=True)
class PromotionCorpus:
    title_to_ref: dict[str, str]   # normalize_claim(title) -> "proposition:<slug>"
    existing_slugs: set[str]       # bare slugs of existing propositions
    derived_refs: set[str]         # annotation: refs already in some proposition's source_refs


@dataclass(frozen=True)
class PromotionCandidate:
    ref: str
    frag: str
    claim: str
    subject: str | None
    object: str | None
    decision: str           # MINT | LINK | COLLISION | SKIP
    slug: str | None        # MINT: new bare slug; LINK: "proposition:<slug>"; else None
    reason: str             # short explanation / skip reason


def decide_candidates(promotables: list[Promotable], corpus: PromotionCorpus) -> list[PromotionCandidate]:
    """Pure mint-or-link-or-collision decision. Detects intra-batch slug collisions."""
    out: list[PromotionCandidate] = []
    minted_slugs: set[str] = set()
    for p in promotables:
        key = normalize_claim(p.claim)
        existing = corpus.title_to_ref.get(key)
        if existing is not None:
            out.append(_cand(p, "LINK", existing, "normalized claim equals existing proposition title"))
            continue
        try:
            slug = slug_for_claim_text(p.claim)
        except EntityCommandError:
            out.append(_cand(p, "SKIP", None, "promote-claim-unsluggable"))
            continue
        if slug in corpus.existing_slugs:
            out.append(_cand(p, "COLLISION", slug, "promote-slug-collision"))  # vs existing corpus
            continue
        if slug in minted_slugs:
            out.append(_cand(p, "COLLISION", slug, "promote-slug-collision"))  # intra-batch
            continue
        minted_slugs.add(slug)
        out.append(_cand(p, "MINT", slug, "new proposition"))
    return out


def _cand(p: Promotable, decision: str, slug: str | None, reason: str) -> PromotionCandidate:
    return PromotionCandidate(
        ref=p.ref, frag=p.frag, claim=p.claim, subject=p.subject, object=p.object,
        decision=decision, slug=slug, reason=reason,
    )
