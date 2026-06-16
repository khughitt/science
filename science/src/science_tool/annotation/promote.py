"""Phase 4a — statement→proposition promotion (decision + apply)."""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from science_model.propositions import PropositionEntity
from science_model.templates import Renderer

from science_tool.annotation import io as anno_io
from science_tool.annotation.model import Status, TextualBody
from science_tool.annotation.query import entity_relpath_for_sidecar, read_sidecar_strict
from science_tool.entities import (
    EntityCommandError,
    _atomic_replace_text,
    _parse_markdown_file,
    append_entity_source_ref,
    default_status,
    resolve_path_policy,
    slug_for_claim_text,
    write_entity_file,
)
from science_tool.entity_reservation import reserve_entity


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
    kind: str = "proposition"   # promotable kind: proposition | question | hypothesis


@dataclass(frozen=True)
class PromotionCorpus:
    title_to_ref: dict[str, str]      # normalize_claim(title) -> "<kind>:<local_part>" (first-wins)
    existing_slugs: set[str]          # bare local-parts of existing entities of this kind
    derived_refs: set[str]            # annotation: refs already in some entity's source_refs (global)
    ambiguous_titles: set[str] = field(default_factory=set)  # normalized titles held by >=2 entities


@dataclass(frozen=True)
class PromotionCandidate:
    ref: str
    frag: str
    claim: str
    subject: str | None
    object: str | None
    decision: str           # MINT | LINK | COLLISION | SKIP
    slug: str | None        # MINT: new bare local-part; LINK: "<kind>:<local_part>"; else None
    reason: str             # short explanation / skip reason
    kind: str = "proposition"


def decide_candidates(
    promotables: list[Promotable],
    corpus: PromotionCorpus,
    *,
    slug_addressed: bool = True,
) -> list[PromotionCandidate]:
    """Pure mint-or-link-or-collision decision for one kind's promotables.

    Detects intra-batch slug collisions. `slug_addressed` True (proposition) keeps the 4a
    slug-collision detection; False (numeric question/hypothesis) skips it — numeric
    reservation cannot collide.
    """
    out: list[PromotionCandidate] = []
    minted_slugs: set[str] = set()
    for p in promotables:
        key = normalize_claim(p.claim)
        if key in corpus.ambiguous_titles:
            out.append(_cand(p, "SKIP", None, "promote-link-ambiguous"))
            continue
        existing = corpus.title_to_ref.get(key)
        if existing is not None:
            out.append(_cand(p, "LINK", existing, "normalized claim equals existing entity title"))
            continue
        try:
            slug = slug_for_claim_text(p.claim)
        except EntityCommandError:
            out.append(_cand(p, "SKIP", None, "promote-claim-unsluggable"))
            continue
        if slug_addressed:
            if slug in corpus.existing_slugs:
                out.append(_cand(p, "COLLISION", slug, "promote-slug-collision"))  # vs existing corpus
                continue
            if slug in minted_slugs:
                out.append(_cand(p, "COLLISION", slug, "promote-slug-collision"))  # intra-batch
                continue
            minted_slugs.add(slug)
        out.append(_cand(p, "MINT", slug, "new entity"))
    return out


def _cand(p: Promotable, decision: str, slug: str | None, reason: str) -> PromotionCandidate:
    return PromotionCandidate(
        ref=p.ref, frag=p.frag, claim=p.claim, subject=p.subject, object=p.object,
        decision=decision, slug=slug, reason=reason, kind=p.kind,
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


PROMOTABLE_KINDS: tuple[str, ...] = ("proposition", "question", "hypothesis")

# (candidate, source_refs, project_root, as_of) -> minted entity id "<kind>:<local_part>"
MintFn = Callable[["PromotionCandidate", list[str], Path, "date | None"], str]


@dataclass(frozen=True)
class PromotionTarget:
    kind: str
    slug_addressed: bool   # proposition True (content-addressed slug); numeric kinds False
    mint: MintFn


def entity_dest(entity_id: str, project_root: Path) -> Path:
    """Canonical file path for `<kind>:<local_part>` (works for slug + numeric kinds)."""
    kind, local_part = entity_id.split(":", 1)
    policy = resolve_path_policy(kind, project_root=project_root)
    return project_root / policy.root / f"{local_part}.md"


def _mint_proposition(
    c: PromotionCandidate, source_refs: list[str], project_root: Path, as_of: date | None
) -> str:
    """4a proposition mint: slug-addressed write_entity_file + never-overwrite guard."""
    assert c.slug is not None
    prop_ref = f"proposition:{c.slug}"
    dest = entity_dest(prop_ref, project_root)
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
        source_refs=list(source_refs),
    )
    write_entity_file(prop, project_root=project_root, body=_proposition_body(c.claim), as_of=as_of)
    return prop_ref


def proposition_target() -> PromotionTarget:
    return PromotionTarget(kind="proposition", slug_addressed=True, mint=_mint_proposition)


_LEAD_SECTION: dict[str, str] = {
    "question": "Summary",
    "hypothesis": "Organizing Conjecture",
}


def _insert_claim_into_lead(rendered: str, section_name: str, claim: str) -> str:
    """Insert the verbatim claim as the first body line under `## {section_name}`."""
    marker = f"## {section_name}\n"
    idx = rendered.find(marker)
    if idx == -1:
        raise PromotionApplyError(f"rendered template missing lead section '## {section_name}'")
    at = idx + len(marker)
    return f"{rendered[:at]}\n{claim}\n{rendered[at:]}"


def _mint_numeric(kind: str) -> MintFn:
    lead = _LEAD_SECTION[kind]

    def mint(c: PromotionCandidate, source_refs: list[str], project_root: Path, as_of: date | None) -> str:
        assert c.slug is not None
        today = (as_of or date.today()).isoformat()
        # (1) Preflight the template (pure read, no number consumed). Raises if the packaged
        #     template is missing/malformed — a loud environment error.
        renderer = Renderer()
        renderer.sections(kind)
        # (2) Reserve the number atomically (empty placeholder .md backs the claimed number).
        reservation = reserve_entity(project_root, kind, title=c.claim, slug=c.slug)
        try:
            # (3) Render template-faithful with the real id, then insert the claim into the lead.
            fields: dict[str, object] = {
                "entity_id": reservation.entity_id,
                "title": c.claim,
                "status": default_status(kind),
                "source_refs": list(source_refs),
                "related": [],
                "created": today,
                "updated": today,
            }
            if kind == "hypothesis":
                fields["phase"] = "candidate"
            rendered = renderer.render(kind, fields=fields)
            rendered = _insert_claim_into_lead(rendered, lead, c.claim)
            # (4) Final write — overwrites the empty placeholder. Last step.
            _atomic_replace_text(reservation.path, rendered)
        except Exception as exc:  # explicit post-reservation rollback, then fail loud
            reservation.path.unlink(missing_ok=True)
            if isinstance(exc, PromotionApplyError):
                raise
            raise PromotionApplyError(
                f"failed to write {kind} {reservation.entity_id}: {exc}"
            ) from exc
        return reservation.entity_id

    return mint


def numeric_target(kind: str) -> PromotionTarget:
    if kind not in ("question", "hypothesis"):
        raise ValueError(f"numeric_target supports question/hypothesis, got {kind!r}")
    return PromotionTarget(kind=kind, slug_addressed=False, mint=_mint_numeric(kind))


def build_targets() -> dict[str, PromotionTarget]:
    return {
        "proposition": proposition_target(),
        "question": numeric_target("question"),
        "hypothesis": numeric_target("hypothesis"),
    }


def apply_candidates(
    candidates: list[PromotionCandidate],
    *,
    sidecar_path: Path,
    project_root: Path,
    paper_ref: str,
    as_of: date | None = None,
    targets: dict[str, PromotionTarget] | None = None,
) -> ApplyReport:
    """Execute MINT/LINK candidates: mint via the per-kind target, accrue provenance, backlink."""
    targets = targets if targets is not None else build_targets()
    report = ApplyReport()
    backlinks: dict[str, str] = {}  # frag -> "<kind>:<local_part>"

    for c in candidates:
        if c.decision == "MINT":
            new_id = targets[c.kind].mint(c, [paper_ref, c.ref], project_root, as_of)
            report.written_paths.append(str(entity_dest(new_id, project_root)))
            report.minted += 1
            backlinks[c.frag] = new_id
        elif c.decision == "LINK":
            assert c.slug is not None  # "<kind>:<local_part>"
            dest = entity_dest(c.slug, project_root)
            # Accrue BOTH provenance refs onto the existing entity; append_entity_source_ref
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


class PromotionOverrideError(Exception):
    """Raised when an edited candidate override is invalid (fail loud)."""


def apply_overrides(
    base: list[PromotionCandidate],
    edited_rows: list[dict],
    *,
    existing_refs: set[str],
) -> list[PromotionCandidate]:
    """Overlay curator edits onto freshly computed base candidates, matched by `annotation` ref.

    `edited_rows` is the SAME row shape the read-only `--json` emits
    (`{annotation, decision, slug, ...}`); the curator edits `decision`/`slug` in place. A row
    may switch a candidate to LINK (`slug` = an existing `proposition:<slug>`) or MINT (`slug`
    = the explicit mint slug, bare or `proposition:`-prefixed). Unknown refs and unknown LINK
    targets fail loud. The explicit-id overwrite guard lives at the write boundary
    (`apply_candidates`)."""
    by_ref = {c.ref: c for c in base}
    edited: dict[str, dict] = {}
    for row in edited_rows:
        ref = row.get("annotation")
        if ref not in by_ref:
            raise PromotionOverrideError(f"override row names unknown annotation ref {ref!r}")
        edited[ref] = row
    out: list[PromotionCandidate] = []
    for c in base:
        row = edited.get(c.ref)
        if row is None:
            out.append(c)
            continue
        decision = row.get("decision", c.decision)
        slug = row.get("slug", c.slug)
        if decision == c.decision and slug == c.slug:
            out.append(c)  # untouched row (incl. unedited COLLISION/SKIP) — passthrough
            continue
        if decision == "LINK":
            if not slug or slug not in existing_refs:
                raise PromotionOverrideError(f"LINK target {slug!r} is not an existing proposition")
            out.append(dataclasses.replace(c, decision="LINK", slug=slug, reason="curator override: link"))
        elif decision == "MINT":
            bare = slug.split(":", 1)[1] if isinstance(slug, str) and slug.startswith("proposition:") else slug
            if not bare:
                raise PromotionOverrideError(f"MINT override for {c.ref!r} requires a slug")
            out.append(dataclasses.replace(c, decision="MINT", slug=bare, reason="curator override: mint"))
        else:
            raise PromotionOverrideError(f"override decision for {c.ref!r} must be LINK or MINT, got {decision!r}")
    return out
