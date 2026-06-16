"""Phase 4a — statement→proposition promotion (decision + apply)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from science_tool.annotation.model import Status, TextualBody
from science_tool.annotation.query import entity_relpath_for_sidecar
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


class PromotionReadError(Exception):
    """Raised when a promotable annotation's statement body cannot be read (fail loud)."""


def _annotation_ref(sidecar_path: Path, root: Path, frag: str) -> str:
    return f"annotation:{entity_relpath_for_sidecar(sidecar_path, root)}#{frag}"


def _statement_subject_object(ann) -> tuple[str | None, str | None]:
    """Parse the annotation's JSON statement body for free-text subject/object phrases.

    The statement body is REQUIRED on a proposition annotation: a missing or unparseable
    body is a hard failure (per spec), not a silent subject/object drop.
    """
    for body in ann.bodies:
        if isinstance(body, TextualBody) and body.format == "application/json":
            try:
                data = json.loads(body.value)
            except json.JSONDecodeError as exc:
                raise PromotionReadError(f"annotation {ann.id}: malformed JSON statement body: {exc}") from exc
            if not isinstance(data, dict):
                raise PromotionReadError(f"annotation {ann.id}: statement body is not a JSON object")
            return data.get("subject"), data.get("object")
    raise PromotionReadError(f"annotation {ann.id}: no application/json statement body")


def collect_promotable(sidecar, sidecar_path: Path, root: Path, *, derived_refs: set[str]) -> tuple[list[Promotable], Counter]:
    """Filter a sidecar to the promotable proposition queue, counting skip reasons."""
    out: list[Promotable] = []
    skipped: Counter = Counter()
    for ann in sidecar.annotations:
        if ann.annotation_type != "proposition":
            skipped["promote-not-proposition-type"] += 1
            continue
        if ann.status not in (Status.OPEN, Status.ACK):
            skipped["promote-inactive-status"] += 1
            continue
        ref = _annotation_ref(sidecar_path, root, ann.id)
        if ann.promoted_to is not None or ref in derived_refs:
            skipped["promote-already-promoted"] += 1
            continue
        subject, object_ = _statement_subject_object(ann)
        out.append(Promotable(ref=ref, frag=ann.id, claim=ann.target.selector.exact, subject=subject, object=object_))
    return out, skipped


def load_corpus(project_root: Path) -> PromotionCorpus:
    """Build the proposition corpus (title index, slug set, already-derived refs) from disk."""
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(project_root.resolve())
    title_to_ref: dict[str, str] = {}
    existing_slugs: set[str] = set()
    derived_refs: set[str] = set()
    for entity in sources.entities:
        if entity.kind != "proposition":
            continue
        ref = entity.canonical_id  # "proposition:<slug>"
        existing_slugs.add(ref.split(":", 1)[1])
        title = (entity.title or "").strip()
        if title:
            title_to_ref.setdefault(normalize_claim(title), ref)
        for sref in entity.source_refs:
            if isinstance(sref, str) and sref.startswith("annotation:"):
                derived_refs.add(sref)
    return PromotionCorpus(title_to_ref=title_to_ref, existing_slugs=existing_slugs, derived_refs=derived_refs)
