# science/src/science_tool/entity_import.py
"""Import a loose markdown document as a canonical entity.

`create_entity` mints an entity from a title and a TEMPLATE; import takes a file
that already has content, proposes an id for it, gives it frontmatter, relocates
it, and repoints every reference in both directions.

Three properties the naive version does not have:

  * The preview is READ-ONLY. Id proposal goes through `propose_number`, not
    `reserve_entity` -- the latter commits the .md, so a dry run would leave an
    empty entity and the apply would mint a different number than the preview
    showed.
  * The preview VALIDATES. It renders the exact final text and runs it through
    `_validate_prospective_write`, the same boundary `create_entity` uses. A
    standalone `entities import --apply` must not depend on a later external
    validator to discover it wrote an invalid entity.
  * References move BOTH ways. Inbound refs are repointed at the new id/path, and
    the document's own relative links are rebased -- they resolve against its
    directory, which the move changes.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel

from science_tool.entities import (
    LOCAL_PART_WIDTH,
    EntityCommandError,
    _render_markdown,
    _validate_prospective_write,
    default_status,
    derive_slug,
    resolve_path_policy,
    valid_statuses,
    validate_slug,
)
from science_tool.entity_reservation import claim_number_in_dir, propose_number
from science_tool.markdown_scan import iter_prose_matches
from science_tool.reference_rewrite import (
    _LINK_RE,
    _REMOVABLE_FRONTMATTER_REF_KEYS,
    RELATIONS_KEY,
    RELATIONS_TARGET_KEY,
    RewriteReport,
    _resolve_link,
    _split_target,
    apply_reference_rewrite,
    plan_reference_rewrite,
    rewrite_outbound_links,
)
from science_tool.text_scan import _CODE_SUFFIXES, iter_scannable_files, read_text_or_skip
from science_model.frontmatter import split_frontmatter  # single-read frontmatter parse

_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


class EntityImportError(Exception):
    """A loose-file import could not be planned or applied."""


class ImportPlan(BaseModel):
    """What an import would do. Produced read-only; consumed by apply_import."""

    # The resolved project root the plan was DERIVED against. A plan is an
    # approval of edits to one specific corpus; two checkouts can hold identical
    # bytes, so nothing else in the plan would notice being replayed against the
    # wrong one -- drift detection compares the plan to the corpus, and both
    # corpora agree. Path identity is the right test: a moved or copied checkout
    # SHOULD force a fresh preview.
    project_root: str
    source_rel: str
    # sha256 of the source bytes the plan was rendered from. apply verifies the
    # source still hashes to this before it moves it: a plan carries a fixed
    # `rendered_text`, so an edit to the source made while the preview is reviewed
    # would otherwise be silently discarded -- apply would write the stale render
    # and unlink the newer source. Path-existence is not enough; content is.
    source_sha256: str
    entity_id: str
    kind: str  # claim_number_in_dir needs it to re-check the archive at apply time
    number: int
    dest_rel: str
    title: str
    status: str
    frontmatter: dict[str, Any]
    rendered_text: str
    ref_report: RewriteReport
    warnings: list[str] = []


def _derive_title(text: str, source: Path) -> str:
    match = _HEADING_RE.search(text)
    if match is not None:
        return match.group(1).strip()
    raise EntityImportError(f"{source} has no level-1 heading to derive a title from; pass --title explicitly")


def plan_import(
    project_root: Path,
    source: Path,
    *,
    kind: str,
    title: str | None = None,
    status: str | None = None,
    slug: str | None = None,
    today: date | None = None,
    exclude: frozenset[Path] = frozenset(),
) -> ImportPlan:
    """Plan the import of a loose markdown file. Touches nothing."""
    project_root = Path(project_root).resolve()
    source = Path(source).resolve()

    if not source.is_file():
        raise EntityImportError(f"source not found: {source}")

    # ONE read of the source. `_parse_markdown_file` re-opened the path, so a
    # source changing between the two reads produced a plan whose title/body and
    # whose hash described different bytes. split_frontmatter parses the text we
    # already hold, and that same text is what the hash below commits to.
    text = source.read_text(encoding="utf-8")
    source_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    frontmatter, body = split_frontmatter(text)
    if frontmatter:
        raise EntityImportError(
            f"{source} already has frontmatter; import is for loose documents. "
            "An entity that already carries an id needs a move, not an import."
        )

    resolved_title = title if title is not None else _derive_title(text, source)

    # Identity resolution: everything here calls into entities.py / entity_reservation.py,
    # which raise their OWN exception types (a bare KeyError for a kind unknown to both the
    # built-in table and the local manifest; EntityCommandError for an unsupported kind, a
    # non-numeric kind, or an unsluggable title) on bad user input. plan_import advertises
    # EntityImportError as its sole error type -- every test in this module raises it -- so
    # a caller catching EntityImportError must not see these leak through unwrapped.
    try:
        resolved_status = status if status is not None else default_status(kind, project_root=project_root)
        allowed = valid_statuses(kind, project_root=project_root)
        # None is an OPEN set (entities.py:1697), not an empty one -- do not refuse on it.
        # This check raises EntityImportError directly, which the except clauses below do
        # NOT catch (it is unrelated to EntityCommandError/KeyError) -- it passes through
        # unwrapped, exactly as if it sat outside the try.
        if allowed is not None and resolved_status not in allowed:
            raise EntityImportError(
                f"status {resolved_status!r} is not in the {kind} vocabulary {sorted(allowed)}"
            )
        number = propose_number(project_root, kind)
        slug_value = validate_slug(slug) if slug is not None else derive_slug(resolved_title)
        policy = resolve_path_policy(kind)
    except KeyError as exc:
        raise EntityImportError(f"unknown entity kind: {kind}") from exc
    except EntityCommandError as exc:
        raise EntityImportError(str(exc)) from exc

    local_part = f"{number:0{LOCAL_PART_WIDTH}d}-{slug_value}"
    entity_id = f"{kind}:{local_part}"

    dest = project_root / policy.root / f"{local_part}.md"
    source_rel = source.relative_to(project_root).as_posix()
    dest_rel = dest.relative_to(project_root).as_posix()

    body_rebased, _outbound_hits = rewrite_outbound_links(
        body, PurePosixPath(source_rel).parent, PurePosixPath(dest_rel).parent
    )

    stamp = (today or date.today()).isoformat()
    new_frontmatter: dict[str, Any] = {
        "kind": kind,
        "title": resolved_title,
        "status": resolved_status,
        "created": stamp,
        "updated": stamp,
        "id": entity_id,
    }
    rendered_text = _render_markdown(new_frontmatter, body_rebased)

    warnings, _sources = _validate_prospective_write(
        project_root=project_root,
        rel_path=Path(dest_rel),
        text=rendered_text,
        target_entity_id=entity_id,
    )

    # Exclude the moved source from the INBOUND scan. Its own links are rebased by
    # rewrite_outbound_links above; scanning it again as an inbound referrer would
    # turn a prose mention of its own path into a ManualHit that, come apply, has
    # vanished (apply unlinks the source before the fresh scan) -- so a
    # self-referential document would drift against its own plan every time.
    ref_report = plan_reference_rewrite(
        project_root,
        id_substitutions={source_rel: entity_id},
        path_substitutions={source_rel: dest_rel},
        exclude=exclude | frozenset({source}),
    )

    return ImportPlan(
        project_root=str(project_root),
        source_rel=source_rel,
        source_sha256=source_sha256,
        entity_id=entity_id,
        kind=kind,
        number=number,
        dest_rel=dest_rel,
        title=resolved_title,
        status=resolved_status,
        frontmatter=new_frontmatter,
        rendered_text=rendered_text,
        ref_report=ref_report,
        warnings=list(warnings),
    )


@dataclass(frozen=True)
class _FileState:
    """What a path was, not merely what bytes it held.

    `mode` and `symlink_target` are the v3 gap. `atomic_write_text`
    (`science_model/frontmatter.py:69`) writes a temp file and `os.replace`s it,
    which takes the TEMP file's mode (0600 by umask) and replaces a symlink with
    a regular file. A bytes-only snapshot restores the content and silently
    keeps the mode change and the de-symlinking -- and a bytes-only `_tree`
    comparison in the tests is equally blind to both.
    """

    existed: bool
    is_symlink: bool = False
    symlink_target: str | None = None
    mode: int | None = None
    payload: bytes | None = None


@dataclass(frozen=True)
class _TreeSnapshot:
    files: dict[Path, _FileState]
    dirs: dict[Path, bool]  # path -> existed before


def _capture(path: Path) -> _FileState:
    if path.is_symlink():
        return _FileState(
            existed=True,
            is_symlink=True,
            symlink_target=os.readlink(path),
            mode=path.lstat().st_mode & 0o777,
        )
    if not path.exists():
        return _FileState(existed=False)
    return _FileState(
        existed=True, mode=path.stat().st_mode & 0o777, payload=path.read_bytes()
    )


def _snapshot(paths: list[Path]) -> _TreeSnapshot:
    """Full state for every path a move touches, plus ancestor-directory existence.

    `existed=False` is load-bearing: the destination does not exist yet, so a
    snapshot that could not represent absence would leave it behind after a
    failed import as orphaned debris.
    """
    files = {path: _capture(path) for path in paths}
    dirs: dict[Path, bool] = {}
    for path in paths:
        for ancestor in path.parents:
            if ancestor in dirs:
                break
            dirs[ancestor] = ancestor.exists()
    return _TreeSnapshot(files=files, dirs=dirs)


def _restore(snapshot: _TreeSnapshot, *, restrict: set[Path] | None = None) -> None:
    """Roll files back to their snapshot state.

    With `restrict` given, only those paths are restored -- the set this
    transaction actually mutated. This is load-bearing under concurrency: the
    snapshot covers every path the plan MIGHT touch, but if the per-write recheck
    aborts because a later referrer changed under us, that referrer was changed by
    ANOTHER writer and this transaction never wrote it. Restoring it from our
    snapshot would erase the other writer's edit -- the one the recheck was
    defending. `restrict=None` restores everything (the whole-tree rollback
    tests).
    """
    for path, state in snapshot.files.items():
        if restrict is not None and path not in restrict:
            continue
        if not state.existed:
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or path.exists():
            path.unlink()
        if state.is_symlink:
            assert state.symlink_target is not None
            path.symlink_to(state.symlink_target)
            continue
        assert state.payload is not None
        path.write_bytes(state.payload)
        if state.mode is not None:
            path.chmod(state.mode)
    # Deepest first: a parent cannot be removed before its children.
    for directory in sorted(snapshot.dirs, key=lambda d: len(d.parts), reverse=True):
        if snapshot.dirs[directory] or not directory.exists():
            continue
        try:
            directory.rmdir()
        except OSError:
            # Non-empty: something outside this transaction put it there. Leaving
            # it is correct; deleting another writer's work to tidy up is not.
            pass


def audit_moved_references(
    project_root: Path, moved_rel: str, *, exclude: frozenset[Path] = frozenset()
) -> list[str]:
    """Every unresolved reference into or out of `moved_rel`. Empty list means clean.

    Required by design section 2.2 for EVERY move -- import and Tier A archival
    alike -- because rewriting is not verifying. rewrite_outbound_links rebases
    the links it recognises; this reports the ones it did not: a stale inbound
    path, a sibling that itself moved, an anchor that no longer exists.

    Anchors are checked against the target's ATX headings, slugified the way the
    corpus writes them, because a link to `#section-gone` is broken in exactly
    the way a path check cannot see.
    """
    project_root = Path(project_root).resolve()
    moved_path = project_root / moved_rel
    problems: list[str] = []

    # Outbound: every local link in the moved document must resolve. PROSE only --
    # a link in a code fence is an example. The corpus has 73 unresolvable fenced
    # links; auditing them would fail every import, including this one.
    text, skip = read_text_or_skip(moved_path, moved_rel)
    if text is None:
        assert skip is not None
        return [f"{moved_rel}: unreadable after the move ({skip.reason})"]
    moved_dir = PurePosixPath(moved_rel).parent
    for match in iter_prose_matches(_LINK_RE, text):
        head, tail = _split_target(match.group("target"))
        resolved = _resolve_link(head, moved_dir) if head else moved_rel
        if head and resolved is None:
            continue  # external or non-local; not ours to check
        problems.extend(_check_target(project_root, moved_rel, resolved or moved_rel, tail))

    # Outbound structured refs: the moved document's own frontmatter. The claim
    # is a "link/reference audit"; frontmatter refs are references, and v3 checked
    # only inline links -- so an import could repoint a related: entry at a path
    # that does not exist and call the move clean.
    problems.extend(_check_frontmatter_refs(project_root, moved_rel, text))

    # Inbound: nothing may still point at where the document used to be.
    for path in iter_scannable_files(project_root, exclude=exclude):
        rel_path = path.relative_to(project_root).as_posix()
        if path.suffix.lower() in _CODE_SUFFIXES:
            continue  # reported as ManualHit by the rewriter; not auto-resolvable
        other, other_skip = read_text_or_skip(path, rel_path)
        if other is None:
            assert other_skip is not None
            problems.append(f"{rel_path}: unreadable, may reference {moved_rel} ({other_skip.reason})")
            continue
        referrer_dir = PurePosixPath(rel_path).parent
        for match in iter_prose_matches(_LINK_RE, other):
            head, tail = _split_target(match.group("target"))
            resolved = _resolve_link(head, referrer_dir)
            if resolved is None:
                continue
            # Existence only: whether a REFERRER's own fragment resolves is that
            # referrer's outbound concern (caught when *it* is audited), not the
            # moved document's. Re-validating it here would blame moved_rel for
            # every pre-existing bad anchor anyone else points at it with.
            if not (project_root / resolved).exists():
                problems.append(f"{rel_path}: link to missing {resolved}")
        problems.extend(_check_frontmatter_refs(project_root, rel_path, other))
    return sorted(set(problems))


def _check_frontmatter_refs(project_root: Path, rel_path: str, text: str) -> list[str]:
    """Structured refs that name a PATH must resolve; ids are the graph's job.

    Only path-shaped values are checked. A canonical id (`plan:0042-new`) is
    resolved by `science validate` against the entity graph, and duplicating that
    resolution here would be a second, weaker implementation of it.
    """
    frontmatter, _body = split_frontmatter(text)
    if not frontmatter:
        return []

    def _values() -> Iterator[tuple[str, str]]:
        for key in _REMOVABLE_FRONTMATTER_REF_KEYS:
            value = frontmatter.get(key)
            if isinstance(value, str):
                yield key, value
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        yield key, item
        relations = frontmatter.get(RELATIONS_KEY)
        if isinstance(relations, list):
            for relation in relations:
                if isinstance(relation, dict):
                    target = relation.get(RELATIONS_TARGET_KEY)
                    if isinstance(target, str):
                        yield f"{RELATIONS_KEY}[].{RELATIONS_TARGET_KEY}", target

    problems: list[str] = []
    for key, value in _values():
        if ":" in value or not value.endswith(".md"):
            continue  # a canonical id, not a path
        resolved = _resolve_link(value, PurePosixPath(rel_path).parent)
        if resolved is None:
            continue
        if not (project_root / resolved).exists() and not (project_root / value).exists():
            problems.append(f"{rel_path}: {key} points at missing {value}")
    return problems


def _check_target(project_root: Path, referrer_rel: str, target_rel: str, fragment: str) -> list[str]:
    target = project_root / target_rel
    if not target.exists():
        return [f"{referrer_rel}: link to missing {target_rel}"]
    if not fragment.startswith("#"):
        return []
    text, _skip = read_text_or_skip(target, target_rel)
    if text is None:
        return [f"{referrer_rel}: cannot verify anchor {fragment} in unreadable {target_rel}"]
    if _slugify_anchor(fragment[1:]) not in _heading_anchors(text):
        return [f"{referrer_rel}: anchor {fragment} not found in {target_rel}"]
    return []


def _heading_anchors(text: str) -> set[str]:
    return {_slugify_anchor(m.group(1)) for m in re.finditer(r"^#{1,6}\s+(.+?)\s*$", text, re.MULTILINE)}


def _slugify_anchor(value: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", value.strip().lower())
    return re.sub(r"[\s_]+", "-", slug)


def _validate_plan_for_apply(project_root: Path, plan: ImportPlan) -> Path:
    """Reject a persisted plan that does not describe a safe, self-consistent move,
    BEFORE any mutation. Returns the validated, resolved source path.

    A saved plan is an on-disk artifact that can be hand-edited or corrupted
    between preview and apply. `load_import_plan` proves it is well-TYPED; nothing
    proves its path and identity fields are TRUE. `apply_import` then unlinks the
    source and writes the destination, so those fields are untrusted input to a
    filesystem mutation. `Path("/root") / "/etc/x"` silently discards the root and
    `Path("/root") / "../x"` escapes it, so a validly typed plan could otherwise
    name `/etc/passwd`, `../other-repo/file`, or `.git/config` and have apply
    unlink it.
    """
    def _contained(rel: str, label: str) -> Path:
        pure = PurePosixPath(rel)
        if pure.is_absolute() or rel.startswith("/") or ".." in pure.parts:
            raise EntityImportError(f"plan {label} {rel!r} is not a project-relative path")
        resolved = (project_root / rel).resolve()
        if not resolved.is_relative_to(project_root):
            raise EntityImportError(f"plan {label} {rel!r} escapes the project root")
        return resolved

    source = _contained(plan.source_rel, "source")
    _contained(plan.dest_rel, "destination")
    if not plan.source_rel.endswith(".md"):
        raise EntityImportError(f"plan source {plan.source_rel!r} is not a markdown file")

    # Identity: entity_id, kind and number must agree, and the destination must be
    # EXACTLY the canonical path they imply -- computed here, never trusted from the
    # plan. This is what makes dest_rel tamper-evident: it is fully determined by
    # (kind, number, slug), so any other value is a redirect of the write target.
    id_kind, sep, local_part = plan.entity_id.partition(":")
    if not sep or id_kind != plan.kind:
        raise EntityImportError(f"plan entity_id {plan.entity_id!r} disagrees with kind {plan.kind!r}")
    match = re.match(rf"(\d{{{LOCAL_PART_WIDTH}}})-", local_part)
    if match is None or int(match.group(1)) != plan.number:
        raise EntityImportError(f"plan entity_id {plan.entity_id!r} does not carry number {plan.number}")
    expected_dest = f"{resolve_path_policy(plan.kind).root}/{local_part}.md"
    if plan.dest_rel != expected_dest:
        raise EntityImportError(
            f"plan destination {plan.dest_rel!r} is not canonical for {plan.entity_id!r} "
            f"(expected {expected_dest!r})"
        )

    # Frontmatter and rendered text must describe THIS entity: apply writes
    # rendered_text verbatim and never re-renders it, so a mismatch here would land
    # bytes the identity checks above never saw.
    if plan.frontmatter.get("id") != plan.entity_id or plan.frontmatter.get("kind") != plan.kind:
        raise EntityImportError("plan frontmatter id/kind disagree with the entity_id")
    rendered_fm, _body = split_frontmatter(plan.rendered_text)
    if rendered_fm.get("id") != plan.entity_id:
        raise EntityImportError("plan rendered_text frontmatter does not carry the entity_id")

    # And it must still be valid against the CURRENT corpus, not only the one the
    # preview saw -- the same boundary create_entity and plan_import write through.
    _validate_prospective_write(
        project_root=project_root,
        rel_path=Path(plan.dest_rel),
        text=plan.rendered_text,
        target_entity_id=plan.entity_id,
    )
    return source


def apply_import(
    project_root: Path, plan: ImportPlan, *, exclude: frozenset[Path] = frozenset()
) -> dict:
    """Execute an ImportPlan as one unit, restoring what IT changed on failure.

    The snapshot covers the source, the destination, AND every referrer named in
    the plan's ref_report -- because `apply_reference_rewrite` writes referrers
    one at a time, so a failure partway through leaves the earlier ones modified.
    But rollback restores only the paths this transaction actually mutated (see
    `mutated` below), never a referrer another writer changed under us: the
    snapshot bounds what CAN be restored; `mutated` bounds what SHOULD be.

    `exclude` is forwarded to every corpus scan (the drift re-derivation and the
    inbound audit) so the applied plan artifact, if it lives inside the corpus,
    is not read as a referrer to itself.
    """
    project_root = Path(project_root).resolve()
    if plan.project_root != str(project_root):
        raise EntityImportError(
            f"plan was built against {plan.project_root}, not {project_root}; re-run the preview here"
        )
    # Untrusted-plan gate: containment, canonical destination, identity coherence,
    # and prospective-write validity -- all BEFORE a single byte moves.
    source = _validate_plan_for_apply(project_root, plan)
    dest = project_root / plan.dest_rel

    if not source.is_file():
        raise EntityImportError(f"source not found: {plan.source_rel}")

    # The plan carries a fixed rendered_text derived from the source at preview
    # time. If the source changed since, applying would write the stale render and
    # unlink the newer file -- a silent data loss. Verify content, not existence,
    # BEFORE any mutation or snapshot.
    current_source = source.read_text(encoding="utf-8")
    if hashlib.sha256(current_source.encode("utf-8")).hexdigest() != plan.source_sha256:
        raise EntityImportError(
            f"{plan.source_rel} changed since the preview; re-run the preview so the "
            "plan renders the current source"
        )

    touched = [source, dest, *{project_root / hit.rel_path for hit in plan.ref_report.hits}]
    snapshot = _snapshot(touched)

    # Paths THIS transaction has actually mutated. Nothing is "ours" by assumption:
    # `claim_number_in_dir` exclusively creates the destination and RAISES if
    # another writer already holds it, so a failed claim means the destination on
    # disk is a bystander's file -- restoring it from our (absent) snapshot would
    # delete their work. So dest joins `mutated` only after a successful claim, and
    # source only after a successful unlink; referrers are appended by
    # apply_reference_rewrite as each write lands.
    mutated: set[Path] = set()
    written_refs: list[str] = []
    try:
        claim_number_in_dir(project_root, plan.kind, plan.number, dest.stem, plan.rendered_text)
        mutated.add(dest)
        source.unlink()
        mutated.add(source)
        report = apply_reference_rewrite(
            project_root, plan.ref_report, exclude=exclude | frozenset({source, dest}), written=written_refs
        )

        # Design section 2.2: every move ends in an audit that resolves every
        # link, inbound and outbound. Inside the try, so a broken corpus is
        # rolled back rather than reported.
        if problems := audit_moved_references(project_root, plan.dest_rel, exclude=exclude):
            raise EntityImportError(
                "post-move reference audit failed; the import was rolled back:\n  "
                + "\n  ".join(problems)
            )
    except Exception:
        restrict = {*mutated, *(project_root / rel for rel in written_refs)}
        _restore(snapshot, restrict=restrict)
        raise

    return {
        "id": plan.entity_id,
        "source": plan.source_rel,
        "destination": plan.dest_rel,
        "refs_rewritten": [hit.model_dump() for hit in report.hits],
        "manual_refs": [hit.model_dump() for hit in report.manual],
    }
