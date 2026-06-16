"""Phase 4a — statement→proposition promotion (decision + apply)."""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from science_model.propositions import PropositionEntity

from science_tool.annotation import io as anno_io
from science_tool.annotation.model import Status, TextualBody
from science_tool.annotation.query import entity_relpath_for_sidecar, read_sidecar_strict
from science_tool.entities import (
    EntityCommandError,
    _parse_markdown_file,
    append_entity_source_ref,
    resolve_path_policy,
    slug_for_claim_text,
    write_entity_file,
)


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


class PromotionApplyError(Exception):
    """Raised at write time when applying a candidate would overwrite an unrelated proposition."""


@dataclass
class ApplyReport:
    minted: int = 0
    linked: int = 0
    skipped: Counter = field(default_factory=Counter)
    written_paths: list[str] = field(default_factory=list)


def _proposition_body(claim: str) -> str:
    return f"# {claim}\n\n## Claim\n\n{claim}\n\n## Evidence Summary\n\n\n## Caveats\n"


def apply_candidates(
    candidates: list[PromotionCandidate],
    *,
    sidecar_path: Path,
    project_root: Path,
    paper_ref: str,
    as_of: date | None = None,
) -> ApplyReport:
    """Execute MINT/LINK candidates: write entities, accrue provenance, set the sidecar backlink."""
    report = ApplyReport()
    backlinks: dict[str, str] = {}  # frag -> proposition:<slug>

    for c in candidates:
        if c.decision == "MINT":
            assert c.slug is not None
            prop_ref = f"proposition:{c.slug}"
            policy = resolve_path_policy("proposition", project_root=project_root)
            dest = project_root / policy.root / f"{c.slug}.md"
            # Never-overwrite guard: a MINT slug colliding with a DIFFERENT-claim proposition
            # (only reachable via an explicit-id override; auto mints are pre-screened) fails loud.
            if dest.exists():
                existing_fm, _ = _parse_markdown_file(dest)
                if normalize_claim(str(existing_fm.get("title") or "")) != normalize_claim(c.claim):
                    raise PromotionApplyError(
                        f"refusing to overwrite {dest.name}: it holds a different proposition"
                    )
            prop = PropositionEntity(
                id=prop_ref, title=c.claim, subject=c.subject, object=c.object,
                source_refs=[paper_ref, c.ref],
            )
            write_entity_file(prop, project_root=project_root, body=_proposition_body(c.claim), as_of=as_of)
            report.written_paths.append(str(dest))
            report.minted += 1
            backlinks[c.frag] = prop_ref
        elif c.decision == "LINK":
            assert c.slug is not None  # "proposition:<slug>"
            policy = resolve_path_policy("proposition", project_root=project_root)
            dest = project_root / policy.root / f"{c.slug.split(':', 1)[1]}.md"
            # Accrue BOTH provenance refs onto the existing proposition; append_entity_source_ref
            # dedups, preserves the (possibly hand-authored) prose body, and advances `updated`
            # whenever it actually appends a ref.
            for ref in (paper_ref, c.ref):
                append_entity_source_ref(dest, ref, as_of=as_of)
            report.linked += 1
            backlinks[c.frag] = c.slug
        else:  # COLLISION / SKIP — not applied
            report.skipped[c.reason] += 1

    if backlinks:
        sidecar = read_sidecar_strict(sidecar_path)
        new_anns = tuple(
            dataclasses.replace(a, promoted_to=backlinks[a.id]) if a.id in backlinks else a
            for a in sidecar.annotations
        )
        anno_io.write_sidecar(sidecar_path, dataclasses.replace(sidecar, annotations=new_anns))
    return report
