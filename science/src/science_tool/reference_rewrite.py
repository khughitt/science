# science/src/science_tool/reference_rewrite.py
"""Substituting cross-reference rewriter.

`entities._remove_frontmatter_ref` DROPS a reference; a move must REPOINT it.
This is the substituting counterpart, over the surfaces that actually carry
references in this corpus:

  * flat frontmatter keys (`related`, `source_refs`, ...), scalar or list;
  * nested `relations[].target` -- the canonical typed edge, which
    `_REMOVABLE_FRONTMATTER_REF_KEYS` has no entry for even though
    `archive._inbound_live_refs` reads it; and
  * markdown links `[text](target)`, resolved SEMANTICALLY against the referring
    file's directory so that `./x.md`, `../plans/x.md`, and `doc/plans/x.md` are
    recognised as the same target.

Two substitution maps, because the two surfaces want different values: a
frontmatter `related:` entry becomes the new canonical ID, while a markdown link
must remain a PATH. Passing one map for both is what makes a link point at
`plan:0042-new`, which resolves to nothing.

Prose path mentions are REPORTED (`ManualHit`), never rewritten: a path in prose
may be a historical account of where a document used to live, and blind
substitution would rewrite the audit trail the design depends on.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel

from science_model.frontmatter import split_frontmatter

from science_tool.entities import (
    _REMOVABLE_FRONTMATTER_REF_KEYS,
    _atomic_replace_text,
    _render_markdown,
)
from science_tool.markdown_scan import iter_prose_matches, prose_spans
from science_tool.text_scan import (
    _CODE_SUFFIXES,
    Skip,
    iter_scannable_files,
    read_text_or_skip,
)

RELATIONS_KEY = "relations"
RELATIONS_TARGET_KEY = "target"

_LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)\)")
_EXTERNAL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://|^mailto:", re.IGNORECASE)


class ReferenceDriftError(Exception):
    """The corpus no longer matches the plan that was approved."""


class RefHit(BaseModel):
    rel_path: str
    surface: str
    old: str
    new: str
    # sha256 of the referring file's text AS PLANNED. apply refuses when the
    # live file no longer hashes to this, because "same reference, different
    # file" is still a file the reviewer did not approve writing.
    preimage_sha256: str = ""


class ManualHit(BaseModel):
    rel_path: str
    line: int
    text: str


class FileEdit(BaseModel):
    """One file's exact before-hash and after-text.

    The postimage lives in the plan rather than in a side-channel dict so that
    apply WRITES what was reviewed instead of recomputing something that ought
    to agree. It also makes the plan serialisable, which is what lets a preview
    survive between two CLI invocations.
    """

    rel_path: str
    preimage_sha256: str
    postimage: str


class RewriteReport(BaseModel):
    # The substitutions are part of the frozen plan: apply REPLAYS a plan, so it
    # must not be handed a second, possibly different, set of substitutions.
    id_substitutions: dict[str, str] = {}
    path_substitutions: dict[str, str] = {}
    hits: list[RefHit] = []
    manual: list[ManualHit] = []
    skipped: list[Skip] = []
    edits: list[FileEdit] = []


def _split_target(target: str) -> tuple[str, str]:
    """('doc/plans/x.md#frag', ) -> ('doc/plans/x.md', '#frag')."""
    for sep in ("#", "?"):
        if sep in target:
            head, _, tail = target.partition(sep)
            return head, sep + tail
    return target, ""


def _resolve_link(target: str, referrer_dir: PurePosixPath) -> str | None:
    """Resolve a link target to a repo-relative posix path, or None if not local."""
    if not target or _EXTERNAL_RE.match(target) or target.startswith("#"):
        return None
    if target.startswith("/"):
        return None
    joined = referrer_dir / target
    parts: list[str] = []
    for part in joined.parts:
        if part == ".":
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _relative_link(from_dir: PurePosixPath, to_path: str) -> str:
    """A posix relative link from `from_dir` to repo-relative `to_path`."""
    from_parts = list(from_dir.parts)
    to_parts = list(PurePosixPath(to_path).parts)
    common = 0
    while common < len(from_parts) and common < len(to_parts) and from_parts[common] == to_parts[common]:
        common += 1
    ups = [".."] * (len(from_parts) - common)
    downs = to_parts[common:]
    return "/".join(ups + downs) if ups or downs else to_path


def _rewrite_frontmatter(frontmatter: dict[str, Any], substitutions: dict[str, str], rel_path: str) -> list[RefHit]:
    hits: list[RefHit] = []
    for key in _REMOVABLE_FRONTMATTER_REF_KEYS:
        value = frontmatter.get(key)
        if isinstance(value, list):
            rewritten: list[Any] = []
            for item in value:
                if isinstance(item, str) and item in substitutions:
                    hits.append(RefHit(rel_path=rel_path, surface=key, old=item, new=substitutions[item]))
                    rewritten.append(substitutions[item])
                else:
                    rewritten.append(item)
            if rewritten != value:
                frontmatter[key] = rewritten
        elif isinstance(value, str) and value in substitutions:
            hits.append(RefHit(rel_path=rel_path, surface=key, old=value, new=substitutions[value]))
            frontmatter[key] = substitutions[value]

    relations = frontmatter.get(RELATIONS_KEY)
    if isinstance(relations, list):
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            target = relation.get(RELATIONS_TARGET_KEY)
            if isinstance(target, str) and target in substitutions:
                hits.append(
                    RefHit(
                        rel_path=rel_path,
                        surface=f"{RELATIONS_KEY}[].{RELATIONS_TARGET_KEY}",
                        old=target,
                        new=substitutions[target],
                    )
                )
                relation[RELATIONS_TARGET_KEY] = substitutions[target]
    return hits


def _sub_prose_matches(
    pattern: re.Pattern[str], text: str, replace: Callable[[re.Match[str]], str]
) -> str:
    """re.sub restricted to prose. Rebuilds the string from the right, so that
    each match's offsets stay valid while earlier ones are still unedited."""
    out = text
    for match in reversed(list(iter_prose_matches(pattern, text))):
        out = out[: match.start()] + replace(match) + out[match.end() :]
    return out


def _rewrite_links(text: str, rel_path: str, path_substitutions: dict[str, str]) -> tuple[str, list[RefHit]]:
    referrer_dir = PurePosixPath(rel_path).parent
    hits: list[RefHit] = []

    def _replace(match: re.Match[str]) -> str:
        target = match.group("target")
        head, tail = _split_target(target)
        resolved = _resolve_link(head, referrer_dir)
        if resolved is None or resolved not in path_substitutions:
            return match.group(0)
        new_path = path_substitutions[resolved]
        new_target = _relative_link(referrer_dir, new_path) + tail
        hits.append(RefHit(rel_path=rel_path, surface="markdown-link", old=target, new=new_target))
        return f"[{match.group('text')}]({new_target})"

    # Prose only. A link in a code fence is an EXAMPLE: 141 fenced lines in the
    # consumer corpus carry links, and rewriting them edits what a document says
    # rather than where it points. `hits` comes out in reverse document order,
    # so sort before returning -- _scan's ordering is part of the frozen plan.
    out = _sub_prose_matches(_LINK_RE, text, _replace)
    hits.reverse()
    return out, hits


def _manual_hits(
    text: str, rel_path: str, path_substitutions: dict[str, str], *, prose_only: bool
) -> list[ManualHit]:
    """Every surviving mention of a moving path. Call on the FINAL text.

    The rule is simply "the old path still appears here". No shape heuristic:
    v2 excluded lines that LOOKED like a link (`](old`), which was both
    unnecessary and wrong. Unnecessary because a link this pass rewrote no
    longer contains the old path -- it was substituted. Wrong because a link
    that still contains it is one the resolver DECLINED (a root-relative bare
    target, say), and that is precisely the case a human must see.

    prose_only=True for markdown, where a mention inside a fence is an example
    and nagging a human about it every run is how a report becomes noise nobody
    reads. prose_only=False for code files, which are never rewritten, so every
    mention survives and every mention is reported.
    """
    if prose_only:
        spans = prose_spans(text)
        in_prose = lambda pos: any(start <= pos < stop for start, stop in spans)  # noqa: E731
    else:
        in_prose = lambda pos: True  # noqa: E731

    manual: list[ManualHit] = []
    offset = 0
    for lineno, line in enumerate(text.split("\n"), start=1):
        for old in path_substitutions:
            index = line.find(old)
            if index != -1 and in_prose(offset + index):
                manual.append(ManualHit(rel_path=rel_path, line=lineno, text=line.strip()))
                break
        offset += len(line) + 1
    return manual


def rewrite_outbound_links(text: str, old_dir: Path, new_dir: Path) -> tuple[str, list[RefHit]]:
    """Rebase a document's own relative links after it moves from old_dir to new_dir.

    Relative links are resolved against the file's directory, so a move silently
    breaks every one of them. Absolute paths and external URLs are left alone.
    """
    old = PurePosixPath(old_dir.as_posix())
    new = PurePosixPath(new_dir.as_posix())
    hits: list[RefHit] = []

    def _replace(match: re.Match[str]) -> str:
        target = match.group("target")
        head, tail = _split_target(target)
        resolved = _resolve_link(head, old)
        if resolved is None:
            return match.group(0)
        new_target = _relative_link(new, resolved) + tail
        if new_target == target:
            return match.group(0)
        hits.append(RefHit(rel_path=new.as_posix(), surface="outbound-link", old=target, new=new_target))
        return f"[{match.group('text')}]({new_target})"

    out = _sub_prose_matches(_LINK_RE, text, _replace)
    hits.reverse()
    return out, hits


def _scan(
    project_root: Path,
    *,
    id_substitutions: dict[str, str],
    path_substitutions: dict[str, str],
    exclude: frozenset[Path] = frozenset(),
) -> RewriteReport:
    """Derive the edit set. Writes NOTHING. Reads each file EXACTLY once.

    The single read is a correctness requirement, not tidiness. v3 read the file
    for its digest and then called `_parse_markdown_file(path)`, which read it
    again: if the file changed between the two, one derivation combined two
    versions of it, and the digest described neither.

    The postimage travels IN the report (`FileEdit.postimage`) rather than in a
    side-channel dict, so that what apply writes is literally what the reviewer
    approved -- not a recomputation that happens to agree.
    """
    project_root = Path(project_root).resolve()
    report = RewriteReport(
        id_substitutions=dict(id_substitutions),
        path_substitutions=dict(path_substitutions),
    )

    for path in iter_scannable_files(project_root, exclude=exclude):
        rel_path = path.relative_to(project_root).as_posix()
        text, skip = read_text_or_skip(path, rel_path)  # the ONLY read of this file
        if text is None:
            assert skip is not None
            report.skipped.append(skip)
            continue

        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        is_markdown = path.suffix.lower() in {".md", ".markdown"}

        # Code is scanned for visibility only. A path inside a string literal may
        # be constructed or sliced; substituting into it is a code change.
        if path.suffix.lower() in _CODE_SUFFIXES:
            report.manual.extend(_manual_hits(text, rel_path, path_substitutions, prose_only=False))
            continue

        new_text, link_hits = _rewrite_links(text, rel_path, path_substitutions)

        fm_hits: list[RefHit] = []
        if is_markdown:
            frontmatter, _body = split_frontmatter(text)  # from the SAME bytes
            if frontmatter:
                mutable = dict(frontmatter)
                fm_hits = _rewrite_frontmatter(mutable, id_substitutions, rel_path)
                if fm_hits:
                    # Re-render from the LINK-rewritten body, or the two passes clobber each other.
                    _, body_after_links = _split_frontmatter_text(new_text)
                    new_text = _render_markdown(mutable, body_after_links)

        # Manual hits come from the BODY of the FINAL text: a reference the
        # frontmatter pass already rewrote must not also be reported as needing
        # a hand fix, and a link this pass rewrote is no longer a bare mention.
        _, final_body = _split_frontmatter_text(new_text)
        body_offset = len(new_text.split("\n")) - len(final_body.split("\n"))
        for hit in _manual_hits(final_body, rel_path, path_substitutions, prose_only=is_markdown):
            report.manual.append(hit.model_copy(update={"line": hit.line + body_offset}))

        hits = fm_hits + link_hits
        if hits:
            for hit in hits:
                hit.preimage_sha256 = digest
            report.edits.append(
                FileEdit(rel_path=rel_path, preimage_sha256=digest, postimage=new_text)
            )
        report.hits.extend(hits)

    report.hits.sort(key=lambda h: (h.rel_path, h.surface, h.old))
    report.manual.sort(key=lambda m: (m.rel_path, m.line))
    report.skipped.sort(key=lambda s: s.rel_path)
    report.edits.sort(key=lambda e: e.rel_path)
    return report


def _split_frontmatter_text(text: str) -> tuple[str, str]:
    """Split rendered markdown into (frontmatter_block, body). Mirrors entities' fence."""
    match = re.match(r"^---\n[\s\S]*?\n---\n?", text)
    if match is None:
        return "", text
    return match.group(0), text[match.end() :]


def plan_reference_rewrite(
    project_root: Path,
    *,
    id_substitutions: dict[str, str],
    path_substitutions: dict[str, str],
    exclude: frozenset[Path] = frozenset(),
) -> RewriteReport:
    """Report every reference a rewrite would change. Touches nothing."""
    return _scan(
        project_root,
        id_substitutions=id_substitutions,
        path_substitutions=path_substitutions,
        exclude=exclude,
    )


def apply_reference_rewrite(
    project_root: Path,
    plan: RewriteReport,
    *,
    exclude: frozenset[Path] = frozenset(),
    written: list[str] | None = None,
) -> RewriteReport:
    """Replay an approved plan. Verifies the corpus still matches it, then writes.

    `plan` is the frozen edit set, not a request to recompute one. The corpus is
    re-derived and compared against it; ANY difference -- a new referrer, a
    vanished one, a changed preimage, a new skip -- raises ReferenceDriftError
    and writes nothing.

    Why this is not paranoia: the caller (entities.apply_import) snapshots the
    files named in `plan.hits` so it can roll back. If apply wrote a file the
    plan did not name, that file would be mutated OUTSIDE the snapshot, and a
    later failure would restore everything except it. This check is what makes
    "the snapshot covers everything apply touches" a fact rather than a hope.

    `written`, if given, has each edit's rel_path APPENDED the instant its write
    lands. On a mid-replay raise it holds exactly the files this call changed, so
    the caller can restore ONLY those -- never a referrer a concurrent writer
    touched but this transaction never wrote. `exclude` is forwarded to the fresh
    scan so the applied plan artifact does not re-enter the corpus as a referrer.
    """
    project_root = Path(project_root).resolve()

    if plan.skipped:
        raise ReferenceDriftError(
            "refusing to apply while files could not be read: "
            + "; ".join(f"{s.rel_path} ({s.reason})" for s in plan.skipped)
        )

    fresh = _scan(
        project_root,
        id_substitutions=plan.id_substitutions,
        path_substitutions=plan.path_substitutions,
        exclude=exclude,
    )
    if fresh != plan:
        raise ReferenceDriftError(
            "the corpus changed since the preview; re-run the preview. "
            + _describe_drift(plan, fresh)
        )

    # Write the plan's OWN postimages, and recheck each preimage at its own write
    # boundary. The corpus-wide comparison above closed the preview-to-apply
    # window; this closes the verify-to-write one. They are different windows:
    # the scan reads file N early and writes it late, so a change landing in
    # between would otherwise be overwritten here and then erased a second time
    # when the caller's rollback restored the still-older snapshot.
    #
    # This does NOT make the sequence atomic -- a change between this check and
    # the os.replace a microsecond later is still possible. It converts the
    # exposure from "the whole scan+write pass" to "two adjacent statements",
    # which is the best a lock-free design gets. The project lock belongs in
    # plan 2, where batches make the window matter; see the deliberate-gaps list.
    for edit in plan.edits:
        path = project_root / edit.rel_path
        current, skip = read_text_or_skip(path, edit.rel_path)
        if current is None:
            assert skip is not None
            raise ReferenceDriftError(f"{edit.rel_path} became unreadable mid-apply ({skip.reason})")
        if hashlib.sha256(current.encode("utf-8")).hexdigest() != edit.preimage_sha256:
            raise ReferenceDriftError(
                f"{edit.rel_path} changed between verification and its write; re-run the preview"
            )
        _atomic_replace_text(path, edit.postimage)
        if written is not None:
            written.append(edit.rel_path)  # recorded only AFTER the write lands
    return fresh


def _describe_drift(plan: RewriteReport, fresh: RewriteReport) -> str:
    """Name what moved, so the operator does not have to diff two reports by eye."""
    old_keys = {(h.rel_path, h.surface, h.old, h.new, h.preimage_sha256) for h in plan.hits}
    new_keys = {(h.rel_path, h.surface, h.old, h.new, h.preimage_sha256) for h in fresh.hits}
    parts: list[str] = []
    if added := sorted({k[0] for k in new_keys - old_keys}):
        parts.append(f"new or changed referrers: {', '.join(added)}")
    if removed := sorted({k[0] for k in old_keys - new_keys}):
        parts.append(f"referrers gone or changed: {', '.join(removed)}")
    if fresh.skipped != plan.skipped:
        parts.append(f"unreadable files: {', '.join(s.rel_path for s in fresh.skipped)}")
    if fresh.manual != plan.manual:
        parts.append("manual-hit set changed")
    if {e.rel_path: e.preimage_sha256 for e in fresh.edits} != {
        e.rel_path: e.preimage_sha256 for e in plan.edits
    }:
        parts.append("edit preimages changed")
    return "; ".join(parts) or "reports differ"
