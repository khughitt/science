#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "click>=8.1",
# ]
# ///
"""Apply downstream-project convention migrations.

Read-only by default (`--dry-run`). Pass `--apply` to write changes.

Companion to `scripts/audit_downstream_project_inventory.py`. Implements the
canonical-shape migrations identified in the 2026-04-25 downstream
conventions audit (see `docs/audits/downstream-project-conventions/`) so
each downstream Science project can converge on the upstream conventions
without bespoke per-project scripts.

Rules (selected with `--rule`):

- ``report-id-prefix``: Rewrite frontmatter ``id: doc:DATE-slug`` →
  ``id: report:DATE-slug`` for files directly under
  ``<project>/doc/reports/`` (top level only — not the ``synthesis/``
  subdirectory, which is governed by the synthesis-rollup convention).
  Then rewrite cross-references that previously resolved to those
  drifted ids back to canonical form. Two mention shapes are rewritten:

  - ``doc:reports/DATE-slug`` (entity-ref using the directory infix)
    → ``report:DATE-slug``. Always rewritten when a date-slug follows
    the ``reports/`` infix; directory references such as
    ``doc:reports/synthesis`` are excluded by the date-slug shape.
  - ``doc:DATE-slug`` (bare entity-ref shape) → ``report:DATE-slug``,
    but only when ``<project>/doc/reports/<slug>.md`` exists. This
    path-keying prevents accidentally rewriting bare ``doc:DATE-slug``
    mentions that meant other entity families (e.g. interpretations,
    plans) where the same drift can occur.

  Per audit synthesis §6.3 and follow-on action #5 in the
  conventions-audit-rollout plan, the canonical id prefix for
  ``doc/reports/*.md`` is ``report:``; ``doc:DATE-slug`` is a drift
  shape observed in natural-systems (26/31 reports affected, plus 200+
  bare mentions).

- ``synthesis-type-and-id-rollup``: Canonicalize the synthesis rollup
  file ``<project>/doc/reports/synthesis.md``. Ensures ``type:
  synthesis``, ``id: synthesis:rollup``, and ``report_kind:
  synthesis-rollup``. Defensive against starting ``type:`` values of
  ``report`` / ``synthesis-rollup`` / ``synthesis`` and starting
  ``id:`` values of ``report:synthesis`` / ``report:project-synthesis``
  / absent. Per Q1=C (per the 2026-04-25 synthesis-shape
  investigation), if the rollup carries ``orphan_question_count`` /
  ``orphan_interpretation_count`` / ``orphan_ids``, MOVES those fields
  to the companion ``_emergent-threads.md`` file as a logical-atomic
  apply (both writes succeed or neither does). Mention pass rewrites
  ``report:synthesis`` (literal) and ``report:project-synthesis`` to
  ``synthesis:rollup`` across all tracked markdown.

- ``synthesis-type-and-id-emergent-threads``: Canonicalize
  ``<project>/doc/reports/synthesis/_emergent-threads.md``. Ensures
  ``type: synthesis``, ``id: synthesis:emergent-threads``, and
  ``report_kind: emergent-threads``. Defensive against starting
  ``type:`` values of ``report`` / ``emergent-threads`` /
  ``synthesis`` and starting ``id:`` values of
  ``report:emergent-threads`` /
  ``report:synthesis-emergent-threads`` / absent. Does NOT add or
  modify orphan-count fields — those are managed by the rollup rule's
  atomic-move logic. Mention pass rewrites
  ``report:synthesis-emergent-threads`` and
  ``report:emergent-threads`` to ``synthesis:emergent-threads``.

- ``synthesis-type-and-id-per-hyp``: Canonicalize per-hypothesis
  synthesis files ``<project>/doc/reports/synthesis/*.md`` excluding
  files whose stem starts with ``_``. Ensures ``type: synthesis``,
  ``id: synthesis:<stem>``, and ``report_kind: hypothesis-synthesis``.
  Defensive against starting ``type:`` values of ``report`` /
  ``synthesis`` and starting ``id:`` values of
  ``report:synthesis-<slug>`` / already-canonical
  ``synthesis:<slug>``. No filename-prefix gating (directory placement
  + non-``_`` filename is the discriminator). Mention pass rewrites
  ``report:synthesis-<slug>`` → ``synthesis:<slug>``, path-keyed
  against the per-hyp file stems so non-synthesis ids matching the
  regex are preserved.

- ``pre-registration-id-and-type``: Canonicalize pre-registration
  files matching ``<project>/doc/meta/pre-registration-*.md`` and
  ``<project>/doc/pre-registrations/*.md``. Ensures ``type:
  pre-registration``. Handles two starting ``id:`` shapes:

  - ``id: pre-registration:<slug>`` — already canonical id; just
    rewrite type from ``plan`` (or already ``pre-registration``).
  - ``id: plan:pre-registration-<slug>`` — strip the ``plan:`` prefix
    to ``id: pre-registration:<slug>`` and rewrite type.

  Files whose ``id:`` matches neither pattern (e.g. truly empty
  frontmatter, or NS-style sparse FM with no ``id:``) are SKIPPED —
  they're handled by ``natural-systems-pre-reg-frontmatter``. Mention
  pass rewrites ``plan:pre-registration-<slug>`` →
  ``pre-registration:<slug>``, path-keyed against the pre-reg file
  stems.

- ``natural-systems-pre-reg-frontmatter``: REPORT-ONLY rule (does NOT
  mutate). For files matching ``<project>/doc/meta/pre-registration-*.md``
  whose frontmatter is missing ``id:`` and/or ``type:``, emit a
  per-file canonical-frontmatter suggestion with ``<TODO>``
  placeholders for fields that cannot be derived mechanically
  (``committed:``, ``spec:``). Operator reviews and applies manually.
  Per audit synthesis §3.2 — natural-systems' three sparser pre-reg
  files need human input on these fields.

- ``task-status-canonicalize``: Normalize task ``status:`` values in
  ``<project>/tasks/active.md`` and ``<project>/tasks/done/*.md`` to the
  canonical task-status set ``{active, blocked, deferred, done, proposed,
  retired}``. Drift values mapped:

  - ``completed`` → ``done``
  - ``complete`` → ``done``
  - ``in-progress`` → ``active``
  - ``in_progress`` → ``active``

  Only the ``- status: <value>`` lines inside task blocks (lines starting
  with ``- status:`` or ``status:`` directly under a ``## [tNNN]`` header)
  are touched. Other ``status:`` fields (e.g. document frontmatter) are
  out of scope. Unmapped drift values are left in place and surfaced as
  errors so new drift shapes are not silently masked. Per the recurring
  drift class observed across natural-systems (t324 ``completed``, t328
  ``completed``, t338 ``in-progress``); ``science-tool tasks list`` warns
  on these but does not auto-correct.

- ``specs-frontmatter-backfill``: Add minimal canonical frontmatter to
  ``<project>/specs/*.md`` files that have no frontmatter at all.
  Derives ``id: spec:<basename>`` from the filename, ``title`` from
  the first H1 (``# Title`` line), and ``date: YYYY-MM-DD`` if the
  basename starts with a date. Sets ``type: spec`` and a default
  ``status: design`` (which the project owner may refine afterwards
  to ``approved``, ``superseded``, etc.). Does not touch files that
  already have frontmatter; does not invent ``related_*`` fields.
  Per audit observation: 22 of 32 specs in natural-systems' 2026-03
  cohort were authored before the frontmatter convention solidified
  in 2026-04; the canonical id prefix surfaced from the same audit
  that drove ``report-id-prefix``.

Usage::

    uv run scripts/migrate_downstream_conventions.py <project_root> --rule report-id-prefix
    uv run scripts/migrate_downstream_conventions.py <project_root> --rule report-id-prefix --apply
    uv run scripts/migrate_downstream_conventions.py <project_root> --rule specs-frontmatter-backfill
    uv run scripts/migrate_downstream_conventions.py --self-test

Safety contract:

- Default mode is dry-run. ``--apply`` is required to mutate files.
- The script never mutates ``.git/`` and never invokes mutating git
  commands. It uses ``git ls-files`` only to enumerate tracked markdown
  for the mention-side pass.
- Each rule is intended to be idempotent: re-running ``--apply`` on a
  freshly migrated project must produce zero changes.
- Output is deterministic given a fixed working tree; ordering is
  alphabetical by path.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import click


# ---------- shared infrastructure ----------

_DATE_SLUG = r"\d{4}-\d{2}-\d{2}[A-Za-z0-9_-]*"

# Match ``id: doc:DATE-slug`` (with or without quotes) on a single frontmatter line.
_RE_REPORT_ID_FRONTMATTER = re.compile(
    rf'^(id:\s*)(["\']?)doc:({_DATE_SLUG})\2(\s*)$',
    re.MULTILINE,
)

# Match ``doc:reports/DATE-slug`` entity-ref mentions. Excludes file-path
# strings (``doc/reports/...`` uses ``/`` after ``doc``, not ``:``) and
# directory references like ``doc:reports/synthesis`` or
# ``doc:reports/synthesis/_emergent-threads`` (slug must start with a
# YYYY-MM-DD date).
_RE_REPORT_ID_MENTION = re.compile(rf"(?<![A-Za-z0-9_./-])doc:reports/({_DATE_SLUG})(?![A-Za-z0-9_./-])")

# Match bare ``doc:DATE-slug`` entity-ref mentions (no ``reports/`` infix).
# Path-keyed against the reports directory at substitution time so this only
# rewrites refs that resolve to a known report file.
_RE_REPORT_ID_BARE_MENTION = re.compile(rf"(?<![A-Za-z0-9_./-])doc:({_DATE_SLUG})(?![A-Za-z0-9_./-])")


@dataclass
class FileChange:
    path: Path
    kind: str  # "frontmatter-id" | "mention" | "frontmatter-move" | etc.
    before: str
    after: str
    line_no: int

    def render(self, base: Path | None = None) -> str:
        p = self.path.relative_to(base) if base else self.path
        return f"  {p}:{self.line_no}  [{self.kind}]\n    - {self.before}\n    + {self.after}"


@dataclass
class RuleResult:
    name: str
    changes: list[FileChange] = field(default_factory=list)
    files_touched: set[Path] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)


def _tracked_markdown(project_root: Path) -> list[Path]:
    """Return tracked .md files under ``project_root``.

    Prefers ``git ls-files`` so .gitignored archives/build outputs are
    skipped deterministically. Falls back to rglob for non-git dirs
    (with a small exclusion list for common ignored locations).
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "*.md"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return sorted(project_root / line for line in proc.stdout.splitlines() if line)
    except (subprocess.CalledProcessError, FileNotFoundError):
        excluded = {".git", "node_modules", "archive", "dist", ".venv", ".worktrees"}
        return sorted(p for p in project_root.rglob("*.md") if not (set(p.relative_to(project_root).parts) & excluded))


def _split_frontmatter(text: str) -> tuple[str, str] | None:
    """Return ``(frontmatter_with_delims, body)`` or ``None`` if absent."""
    if not text.startswith("---\n"):
        return None
    rest = text[4:]
    end = rest.find("\n---\n")
    if end < 0:
        return None
    return "---\n" + rest[: end + 1] + "---\n", rest[end + 5 :]


def _record_line_changes(
    result: RuleResult,
    path: Path,
    kind: str,
    before_text: str,
    after_text: str,
    *,
    line_offset: int = 0,
) -> None:
    """Compare ``before_text`` and ``after_text`` line-by-line and append changes."""
    for i, (a, b) in enumerate(zip(before_text.splitlines(), after_text.splitlines()), start=1 + line_offset):
        if a != b:
            result.changes.append(FileChange(path=path, kind=kind, before=a.strip(), after=b.strip(), line_no=i))


# ---------- rule: report-id-prefix ----------


def apply_rule_report_id_prefix(project_root: Path, *, apply: bool) -> RuleResult:
    """Migrate ``doc:DATE-slug`` → ``report:DATE-slug`` (frontmatter id + mentions)."""
    result = RuleResult(name="report-id-prefix")
    reports_dir = project_root / "doc" / "reports"
    # In-memory cache of pass-1 results so pass 2 sees them in dry-run too.
    pass1_content: dict[Path, str] = {}

    # Pass 1: frontmatter `id:` rewrites in <project>/doc/reports/*.md (top-level only).
    if reports_dir.is_dir():
        for path in sorted(reports_dir.glob("*.md")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as e:
                result.errors.append(f"{path}: read failed: {e}")
                continue
            split = _split_frontmatter(text)
            if split is None:
                continue
            fm, body = split
            new_fm, n = _RE_REPORT_ID_FRONTMATTER.subn(r"\1\2report:\3\2\4", fm)
            if n == 0:
                continue
            _record_line_changes(result, path, "frontmatter-id", fm, new_fm)
            result.files_touched.add(path)
            new_content = new_fm + body
            pass1_content[path] = new_content
            if apply:
                try:
                    path.write_text(new_content, encoding="utf-8")
                except OSError as e:
                    result.errors.append(f"{path}: write failed: {e}")

    # Build report stem set for path-keyed bare-mention rewrite.
    report_stems: set[str] = set()
    if reports_dir.is_dir():
        report_stems = {p.stem for p in reports_dir.glob("*.md") if p.is_file()}

    def _rewrite_bare_mention(match: re.Match[str]) -> str:
        slug = match.group(1)
        if slug in report_stems:
            return f"report:{slug}"
        return match.group(0)

    # Pass 2: entity-ref mention rewrites across all tracked markdown.
    # Reads pass-1 in-memory content for files pass 1 already handled, so we do
    # not re-detect the frontmatter id line as a separate "mention" change.
    for path in _tracked_markdown(project_root):
        if not path.is_file():
            continue
        if path in pass1_content:
            text = pass1_content[path]
        else:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                result.errors.append(f"{path}: read failed: {e}")
                continue
        new_text = _RE_REPORT_ID_MENTION.sub(r"report:\1", text)
        new_text = _RE_REPORT_ID_BARE_MENTION.sub(_rewrite_bare_mention, new_text)
        if new_text == text:
            # Either no matches, or every bare-mention slug was a non-report
            # (the regex matched but `_rewrite_bare_mention` returned the
            # original). Either way there is nothing to record.
            continue
        _record_line_changes(result, path, "mention", text, new_text)
        result.files_touched.add(path)
        if apply:
            try:
                path.write_text(new_text, encoding="utf-8")
            except OSError as e:
                result.errors.append(f"{path}: write failed: {e}")

    return result


# ---------- shared synthesis helpers ----------

# Per-hypothesis synthesis slug regex. Per-hyp slugs are NOT date-prefixed
# (e.g. ``h1-foo``, ``h01-bar``, ``double-categorical-foo``) so we use a
# permissive identifier regex.
_SYNTH_SLUG = r"[A-Za-z0-9_-]+"

# Generic frontmatter-line regexes (re-used across synthesis rules).
_RE_FM_TYPE_ANY = re.compile(
    r'^(?P<prefix>type:\s*)(?P<q>["\']?)(?P<value>[A-Za-z0-9_-]+)(?P=q)(?P<suffix>\s*)$',
    re.MULTILINE,
)
_RE_FM_ID_ANY = re.compile(
    r'^(?P<prefix>id:\s*)(?P<q>["\']?)(?P<value>[^"\'\s]+)(?P=q)(?P<suffix>\s*)$',
    re.MULTILINE,
)
_RE_FM_HAS_ID = re.compile(r"^id:\s*", re.MULTILINE)
_RE_FM_HAS_TYPE = re.compile(r"^type:\s*", re.MULTILINE)
_RE_FM_HAS_REPORT_KIND = re.compile(r"^report_kind:\s*", re.MULTILINE)

# Orphan-count fields managed by Q1=C (rollup → threads atomic move).
_ORPHAN_FIELDS = (
    "orphan_question_count",
    "orphan_interpretation_count",
    "orphan_ids",
)


def _set_or_insert_after_type(
    fm: str,
    field_name: str,
    new_value_line: str,
    *,
    rewrite_existing: bool = True,
) -> tuple[str, bool]:
    """Ensure ``field_name`` is present in ``fm`` with ``new_value_line``.

    If absent, insert immediately after the ``type:`` line. If present and
    ``rewrite_existing`` is True, rewrite the value to match
    ``new_value_line``. Returns ``(new_fm, changed)``.

    ``new_value_line`` must be a complete frontmatter line (e.g.
    ``id: "synthesis:rollup"``) — without trailing newline.
    """
    has_field_re = re.compile(rf"^{re.escape(field_name)}:\s*", re.MULTILINE)
    existing = has_field_re.search(fm)
    if existing is None:
        # Insert after ``type:`` line (must be present at this point).
        type_match = re.search(r'^type:\s*["\']?[A-Za-z0-9_-]+["\']?\s*$', fm, re.MULTILINE)
        if type_match is None:
            return fm, False
        insert_at = type_match.end()
        return fm[:insert_at] + "\n" + new_value_line + fm[insert_at:], True
    if not rewrite_existing:
        return fm, False
    # Rewrite the existing line in place.
    line_re = re.compile(rf"^{re.escape(field_name)}:.*$", re.MULTILINE)
    new_fm, n = line_re.subn(new_value_line, fm, count=1)
    if n == 0 or new_fm == fm:
        return fm, False
    return new_fm, True


def _rewrite_fm_field(fm: str, field_name: str, new_value_line: str) -> tuple[str, bool]:
    """Rewrite an existing ``field_name:`` line in ``fm`` to ``new_value_line``.

    Returns ``(new_fm, changed)``. No-op if the field is absent or already
    equals the target line.
    """
    line_re = re.compile(rf"^{re.escape(field_name)}:.*$", re.MULTILINE)
    m = line_re.search(fm)
    if m is None:
        return fm, False
    if m.group(0) == new_value_line:
        return fm, False
    new_fm = line_re.sub(new_value_line, fm, count=1)
    return new_fm, new_fm != fm


def _strip_fm_field(fm: str, field_name: str) -> tuple[str, str | None]:
    """Strip a single-line ``field_name: value`` entry from ``fm``.

    Returns ``(new_fm, removed_line)`` where ``removed_line`` is the full
    line (without trailing newline) that was removed, or ``None`` if the
    field was absent. Only handles single-line scalar fields (does not
    handle block sequences). For ``orphan_ids`` (which may be ``[]`` or a
    block list) we only handle the inline form ``orphan_ids: [...]`` or
    ``orphan_ids: <scalar>``; multi-line block lists are reported as an
    error to the caller.
    """
    line_re = re.compile(rf"^({re.escape(field_name)}:.*)$\n?", re.MULTILINE)
    m = line_re.search(fm)
    if m is None:
        return fm, None
    removed = m.group(1)
    new_fm = line_re.sub("", fm, count=1)
    return new_fm, removed


# ---------- rule: synthesis-type-and-id-rollup ----------


def _migrate_orphan_fields_to_threads(
    rollup_fm: str, threads_path: Path, *, apply: bool, result: RuleResult
) -> tuple[str, dict[Path, str]]:
    """Move orphan-count fields from ``rollup_fm`` to the threads file.

    Returns ``(new_rollup_fm, threads_writes)`` where ``threads_writes``
    maps the threads path to its new full-file content if it should be
    written (empty if the threads file requires no changes). Atomicity:
    if either the rollup strip or the threads insert fails, NEITHER is
    applied (errors are recorded and an empty dict is returned).
    """
    # Detect whether any orphan field is present on the rollup. If not, no-op.
    present_fields = [f for f in _ORPHAN_FIELDS if re.search(rf"^{re.escape(f)}:\s*", rollup_fm, re.MULTILINE)]
    if not present_fields:
        return rollup_fm, {}

    # Block-list detection for orphan_ids: if `orphan_ids:` is followed by a
    # newline-then-`-` line, we don't have safe machinery to move it as a
    # block. Stop and report.
    block_list_re = re.compile(r"^orphan_ids:\s*$\n(\s+- )", re.MULTILINE)
    if block_list_re.search(rollup_fm):
        result.errors.append(
            f"{threads_path}: rollup has orphan_ids in block-list form; refusing to migrate (move manually)."
        )
        return rollup_fm, {}

    # Strip orphan fields from rollup.
    new_rollup_fm = rollup_fm
    moved_lines: list[str] = []
    for f in present_fields:
        new_rollup_fm, removed = _strip_fm_field(new_rollup_fm, f)
        if removed is None:
            continue
        moved_lines.append(removed)

    # Read threads file (must exist for the move to proceed).
    if not threads_path.is_file():
        result.errors.append(
            f"{threads_path}: rollup carries orphan fields but threads file is missing; cannot atomically move."
        )
        return rollup_fm, {}
    try:
        threads_text = threads_path.read_text(encoding="utf-8")
    except OSError as e:
        result.errors.append(f"{threads_path}: read failed: {e}")
        return rollup_fm, {}
    threads_split = _split_frontmatter(threads_text)
    if threads_split is None:
        result.errors.append(f"{threads_path}: no frontmatter; cannot move orphan fields here.")
        return rollup_fm, {}
    threads_fm, threads_body = threads_split

    # Insert each moved line on the threads file if not already present.
    new_threads_fm = threads_fm
    threads_inserted: list[str] = []
    for line in moved_lines:
        # Extract field name from the line.
        field_match = re.match(r"^([A-Za-z0-9_]+):", line)
        if field_match is None:
            continue
        fname = field_match.group(1)
        if re.search(rf"^{re.escape(fname)}:\s*", new_threads_fm, re.MULTILINE):
            # Already present on threads; don't clobber. Drop the moved
            # value silently (the threads file is the source of truth).
            continue
        # Insert before the closing ``---`` line of the threads frontmatter.
        # _split_frontmatter returns fm including the trailing ``---\n``.
        # Insert right before that final delimiter.
        if not new_threads_fm.endswith("---\n"):
            result.errors.append(f"{threads_path}: malformed frontmatter; refusing to migrate.")
            return rollup_fm, {}
        # Strip the closing delimiter, append the new line, restore.
        body_part = new_threads_fm[:-4]  # strips ``---\n``
        if not body_part.endswith("\n"):
            body_part += "\n"
        new_threads_fm = body_part + line + "\n---\n"
        threads_inserted.append(line)

    if not threads_inserted and new_rollup_fm == rollup_fm:
        return rollup_fm, {}

    # Record changes for the threads side.
    if threads_inserted:
        _record_line_changes(result, threads_path, "frontmatter-move", threads_fm, new_threads_fm)
        result.files_touched.add(threads_path)
        new_threads_full = new_threads_fm + threads_body
        return new_rollup_fm, {threads_path: new_threads_full}
    return new_rollup_fm, {}


def apply_rule_synthesis_type_and_id_rollup(project_root: Path, *, apply: bool) -> RuleResult:
    """Canonicalize the synthesis rollup file (type/id/report_kind + orphan-move)."""
    result = RuleResult(name="synthesis-type-and-id-rollup")
    rollup_path = project_root / "doc" / "reports" / "synthesis.md"
    threads_path = project_root / "doc" / "reports" / "synthesis" / "_emergent-threads.md"

    pass1_content: dict[Path, str] = {}

    if rollup_path.is_file():
        try:
            text = rollup_path.read_text(encoding="utf-8")
        except OSError as e:
            result.errors.append(f"{rollup_path}: read failed: {e}")
        else:
            split = _split_frontmatter(text)
            if split is not None:
                fm, body = split
                new_fm = fm

                # Step 1: ensure `type: "synthesis"`.
                m_type = _RE_FM_TYPE_ANY.search(new_fm)
                if m_type is None:
                    # No `type:` line at all — insert at top of frontmatter
                    # (after the opening ``---\n``) to keep the canonical
                    # cluster intact.
                    new_fm = _insert_top_of_fm(new_fm, 'type: "synthesis"')
                elif m_type.group("value") != "synthesis":
                    new_fm = (
                        new_fm[: m_type.start()]
                        + f'{m_type.group("prefix")}"synthesis"{m_type.group("suffix")}'
                        + new_fm[m_type.end() :]
                    )

                # Step 2: ensure `id: "synthesis:rollup"`.
                m_id = _RE_FM_ID_ANY.search(new_fm)
                target_id_line = 'id: "synthesis:rollup"'
                if m_id is None:
                    # Insert id immediately after the type line (matching
                    # template: id, type, report_kind cluster). Per the spec,
                    # since `type:` is the anchor, we insert AFTER it.
                    new_fm, _ = _set_or_insert_after_type(new_fm, "id", target_id_line, rewrite_existing=False)
                elif m_id.group("value") != "synthesis:rollup":
                    new_fm, _ = _rewrite_fm_field(new_fm, "id", target_id_line)

                # Step 3: ensure `report_kind: "synthesis-rollup"`.
                target_rk_line = 'report_kind: "synthesis-rollup"'
                if _RE_FM_HAS_REPORT_KIND.search(new_fm) is None:
                    new_fm, _ = _set_or_insert_after_type(new_fm, "report_kind", target_rk_line, rewrite_existing=False)
                else:
                    new_fm, _ = _rewrite_fm_field(new_fm, "report_kind", target_rk_line)

                # Step 4: Q1=C orphan-count migration to threads.
                new_fm, threads_writes = _migrate_orphan_fields_to_threads(
                    new_fm, threads_path, apply=apply, result=result
                )

                if new_fm != fm:
                    _record_line_changes(result, rollup_path, "frontmatter-id", fm, new_fm)
                    result.files_touched.add(rollup_path)
                    pass1_content[rollup_path] = new_fm + body
                    if apply:
                        # Atomic apply: write threads first, rollup second.
                        # If threads write fails we won't write the rollup.
                        try:
                            for tp, tcontent in threads_writes.items():
                                tp.write_text(tcontent, encoding="utf-8")
                            rollup_path.write_text(new_fm + body, encoding="utf-8")
                        except OSError as e:
                            result.errors.append(f"{rollup_path}: write failed: {e}")
                elif threads_writes:
                    # Edge case: rollup had no FM canonicalization needed but
                    # orphan-move is still pending (rare). Apply threads only.
                    if apply:
                        try:
                            for tp, tcontent in threads_writes.items():
                                tp.write_text(tcontent, encoding="utf-8")
                        except OSError as e:
                            result.errors.append(f"{tp}: write failed: {e}")

    # Pass 2: mention rewrites for ``report:synthesis`` (literal, no slug)
    # and ``report:project-synthesis`` → ``synthesis:rollup``.
    re_literal = re.compile(r"(?<![A-Za-z0-9_./-])report:synthesis(?![A-Za-z0-9_./:-])")
    re_project = re.compile(r"(?<![A-Za-z0-9_./-])report:project-synthesis(?![A-Za-z0-9_./:-])")

    for path in _tracked_markdown(project_root):
        if not path.is_file():
            continue
        if path in pass1_content:
            text = pass1_content[path]
        else:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                result.errors.append(f"{path}: read failed: {e}")
                continue
        new_text = re_project.sub("synthesis:rollup", text)
        new_text = re_literal.sub("synthesis:rollup", new_text)
        if new_text == text:
            continue
        _record_line_changes(result, path, "mention", text, new_text)
        result.files_touched.add(path)
        if apply:
            try:
                path.write_text(new_text, encoding="utf-8")
            except OSError as e:
                result.errors.append(f"{path}: write failed: {e}")

    return result


def _insert_top_of_fm(fm: str, line: str) -> str:
    """Insert ``line`` immediately after the opening ``---\\n`` of ``fm``."""
    if not fm.startswith("---\n"):
        return fm
    return "---\n" + line + "\n" + fm[4:]


# ---------- rule: synthesis-type-and-id-emergent-threads ----------


def apply_rule_synthesis_type_and_id_emergent_threads(project_root: Path, *, apply: bool) -> RuleResult:
    """Canonicalize ``_emergent-threads.md`` (type/id/report_kind)."""
    result = RuleResult(name="synthesis-type-and-id-emergent-threads")
    path = project_root / "doc" / "reports" / "synthesis" / "_emergent-threads.md"
    pass1_content: dict[Path, str] = {}

    if path.is_file():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            result.errors.append(f"{path}: read failed: {e}")
        else:
            split = _split_frontmatter(text)
            if split is not None:
                fm, body = split
                new_fm = fm

                # Step 1: ensure type.
                m_type = _RE_FM_TYPE_ANY.search(new_fm)
                if m_type is None:
                    new_fm = _insert_top_of_fm(new_fm, 'type: "synthesis"')
                elif m_type.group("value") != "synthesis":
                    new_fm = (
                        new_fm[: m_type.start()]
                        + f'{m_type.group("prefix")}"synthesis"{m_type.group("suffix")}'
                        + new_fm[m_type.end() :]
                    )

                # Step 2: ensure id.
                target_id_line = 'id: "synthesis:emergent-threads"'
                m_id = _RE_FM_ID_ANY.search(new_fm)
                if m_id is None:
                    new_fm, _ = _set_or_insert_after_type(new_fm, "id", target_id_line, rewrite_existing=False)
                elif m_id.group("value") != "synthesis:emergent-threads":
                    new_fm, _ = _rewrite_fm_field(new_fm, "id", target_id_line)

                # Step 3: ensure report_kind.
                target_rk_line = 'report_kind: "emergent-threads"'
                if _RE_FM_HAS_REPORT_KIND.search(new_fm) is None:
                    new_fm, _ = _set_or_insert_after_type(new_fm, "report_kind", target_rk_line, rewrite_existing=False)
                else:
                    new_fm, _ = _rewrite_fm_field(new_fm, "report_kind", target_rk_line)

                if new_fm != fm:
                    _record_line_changes(result, path, "frontmatter-id", fm, new_fm)
                    result.files_touched.add(path)
                    pass1_content[path] = new_fm + body
                    if apply:
                        try:
                            path.write_text(new_fm + body, encoding="utf-8")
                        except OSError as e:
                            result.errors.append(f"{path}: write failed: {e}")

    # Pass 2: mention rewrites for ``report:emergent-threads`` and
    # ``report:synthesis-emergent-threads`` → ``synthesis:emergent-threads``.
    # Order matters: rewrite the longer ``report:synthesis-emergent-threads``
    # first so the ``report:emergent-threads`` regex doesn't see the prefix.
    re_long = re.compile(r"(?<![A-Za-z0-9_./-])report:synthesis-emergent-threads(?![A-Za-z0-9_./:-])")
    re_short = re.compile(r"(?<![A-Za-z0-9_./-])report:emergent-threads(?![A-Za-z0-9_./:-])")
    for p in _tracked_markdown(project_root):
        if not p.is_file():
            continue
        if p in pass1_content:
            text = pass1_content[p]
        else:
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                result.errors.append(f"{p}: read failed: {e}")
                continue
        new_text = re_long.sub("synthesis:emergent-threads", text)
        new_text = re_short.sub("synthesis:emergent-threads", new_text)
        if new_text == text:
            continue
        _record_line_changes(result, p, "mention", text, new_text)
        result.files_touched.add(p)
        if apply:
            try:
                p.write_text(new_text, encoding="utf-8")
            except OSError as e:
                result.errors.append(f"{p}: write failed: {e}")

    return result


# ---------- rule: synthesis-type-and-id-per-hyp ----------


def apply_rule_synthesis_type_and_id_per_hyp(project_root: Path, *, apply: bool) -> RuleResult:
    """Canonicalize per-hypothesis synthesis files (type/id/report_kind)."""
    result = RuleResult(name="synthesis-type-and-id-per-hyp")
    synth_dir = project_root / "doc" / "reports" / "synthesis"
    pass1_content: dict[Path, str] = {}
    synth_stems: set[str] = set()

    if synth_dir.is_dir():
        for path in sorted(synth_dir.glob("*.md")):
            if not path.is_file() or path.stem.startswith("_"):
                continue
            stem = path.stem
            synth_stems.add(stem)
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as e:
                result.errors.append(f"{path}: read failed: {e}")
                continue
            split = _split_frontmatter(text)
            if split is None:
                continue
            fm, body = split
            new_fm = fm

            # Step 1: ensure type.
            m_type = _RE_FM_TYPE_ANY.search(new_fm)
            if m_type is None:
                new_fm = _insert_top_of_fm(new_fm, 'type: "synthesis"')
            elif m_type.group("value") != "synthesis":
                new_fm = (
                    new_fm[: m_type.start()]
                    + f'{m_type.group("prefix")}"synthesis"{m_type.group("suffix")}'
                    + new_fm[m_type.end() :]
                )

            # Step 2: ensure id == synthesis:<stem>.
            target_id_line = f'id: "synthesis:{stem}"'
            m_id = _RE_FM_ID_ANY.search(new_fm)
            if m_id is None:
                new_fm, _ = _set_or_insert_after_type(new_fm, "id", target_id_line, rewrite_existing=False)
            elif m_id.group("value") != f"synthesis:{stem}":
                new_fm, _ = _rewrite_fm_field(new_fm, "id", target_id_line)

            # Step 3: ensure report_kind.
            target_rk_line = 'report_kind: "hypothesis-synthesis"'
            if _RE_FM_HAS_REPORT_KIND.search(new_fm) is None:
                new_fm, _ = _set_or_insert_after_type(new_fm, "report_kind", target_rk_line, rewrite_existing=False)
            else:
                new_fm, _ = _rewrite_fm_field(new_fm, "report_kind", target_rk_line)

            if new_fm != fm:
                _record_line_changes(result, path, "frontmatter-id", fm, new_fm)
                result.files_touched.add(path)
                pass1_content[path] = new_fm + body
                if apply:
                    try:
                        path.write_text(new_fm + body, encoding="utf-8")
                    except OSError as e:
                        result.errors.append(f"{path}: write failed: {e}")

    # Pass 2: mention rewrites for ``report:synthesis-<slug>`` →
    # ``synthesis:<slug>``, path-keyed against ``synth_stems`` so unrelated
    # ids matching the same regex are preserved.
    #
    # Note on path-keying: an existing per-hyp file may have been named
    # differently from the legacy id (e.g. mm30 ships ``h1-foo.md`` with
    # legacy id ``report:synthesis-h1-foo`` — same stem). For projects
    # where the legacy id had a different slug than the file stem (none
    # observed today), this would silently skip the mention. Documented
    # for future debugging.
    mention_re = re.compile(rf"(?<![A-Za-z0-9_./-])report:synthesis-({_SYNTH_SLUG})(?![A-Za-z0-9_./:-])")

    def _rewrite_mention(match: re.Match[str]) -> str:
        slug = match.group(1)
        if slug in synth_stems:
            return f"synthesis:{slug}"
        return match.group(0)

    for path in _tracked_markdown(project_root):
        if not path.is_file():
            continue
        if path in pass1_content:
            text = pass1_content[path]
        else:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                result.errors.append(f"{path}: read failed: {e}")
                continue
        new_text = mention_re.sub(_rewrite_mention, text)
        if new_text == text:
            continue
        _record_line_changes(result, path, "mention", text, new_text)
        result.files_touched.add(path)
        if apply:
            try:
                path.write_text(new_text, encoding="utf-8")
            except OSError as e:
                result.errors.append(f"{path}: write failed: {e}")

    return result


# ---------- rule: pre-registration-id-and-type ----------


_PRE_REG_SLUG = r"[A-Za-z0-9_-]+"
_RE_PREREG_ID_CANONICAL = re.compile(
    rf'^id:\s*(["\']?)pre-registration:({_PRE_REG_SLUG})\1\s*$',
    re.MULTILINE,
)
_RE_PREREG_ID_PLAN_PREFIXED = re.compile(
    rf'^id:\s*(["\']?)plan:pre-registration-({_PRE_REG_SLUG})\1\s*$',
    re.MULTILINE,
)


def apply_rule_pre_registration_id_and_type(project_root: Path, *, apply: bool) -> RuleResult:
    """Canonicalize pre-reg files (type + id), handling both starting id shapes."""
    result = RuleResult(name="pre-registration-id-and-type")

    candidates: list[Path] = []
    meta_dir = project_root / "doc" / "meta"
    if meta_dir.is_dir():
        candidates.extend(sorted(meta_dir.glob("pre-registration-*.md")))
    pre_dir = project_root / "doc" / "pre-registrations"
    if pre_dir.is_dir():
        candidates.extend(sorted(pre_dir.glob("*.md")))

    pass1_content: dict[Path, str] = {}
    canonical_stems: set[str] = set()

    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            result.errors.append(f"{path}: read failed: {e}")
            continue
        split = _split_frontmatter(text)
        if split is None:
            continue
        fm, body = split

        # Determine the canonical slug: prefer the existing canonical id,
        # else the plan-prefixed id, else SKIP (handled by
        # ``natural-systems-pre-reg-frontmatter``).
        m_canon = _RE_PREREG_ID_CANONICAL.search(fm)
        m_plan = _RE_PREREG_ID_PLAN_PREFIXED.search(fm)
        if m_canon is not None:
            slug = m_canon.group(2)
        elif m_plan is not None:
            slug = m_plan.group(2)
        else:
            continue
        canonical_stems.add(slug)

        new_fm = fm

        # Step 1: rewrite plan-prefixed id → canonical id.
        if m_plan is not None and m_canon is None:
            target_id_line = f'id: "pre-registration:{slug}"'
            new_fm, _ = _rewrite_fm_field(new_fm, "id", target_id_line)

        # Step 2: ensure type: "pre-registration".
        m_type = _RE_FM_TYPE_ANY.search(new_fm)
        if m_type is None:
            new_fm = _insert_top_of_fm(new_fm, 'type: "pre-registration"')
        elif m_type.group("value") != "pre-registration":
            new_fm = (
                new_fm[: m_type.start()]
                + f'{m_type.group("prefix")}"pre-registration"{m_type.group("suffix")}'
                + new_fm[m_type.end() :]
            )

        if new_fm != fm:
            _record_line_changes(result, path, "frontmatter-id", fm, new_fm)
            result.files_touched.add(path)
            pass1_content[path] = new_fm + body
            if apply:
                try:
                    path.write_text(new_fm + body, encoding="utf-8")
                except OSError as e:
                    result.errors.append(f"{path}: write failed: {e}")

    # Pass 2: mention rewrites for ``plan:pre-registration-<slug>`` →
    # ``pre-registration:<slug>``, path-keyed against ``canonical_stems``.
    mention_re = re.compile(rf"(?<![A-Za-z0-9_./-])plan:pre-registration-({_PRE_REG_SLUG})(?![A-Za-z0-9_./:-])")

    def _rewrite_mention(match: re.Match[str]) -> str:
        slug = match.group(1)
        if slug in canonical_stems:
            return f"pre-registration:{slug}"
        return match.group(0)

    for path in _tracked_markdown(project_root):
        if not path.is_file():
            continue
        if path in pass1_content:
            text = pass1_content[path]
        else:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                result.errors.append(f"{path}: read failed: {e}")
                continue
        new_text = mention_re.sub(_rewrite_mention, text)
        if new_text == text:
            continue
        _record_line_changes(result, path, "mention", text, new_text)
        result.files_touched.add(path)
        if apply:
            try:
                path.write_text(new_text, encoding="utf-8")
            except OSError as e:
                result.errors.append(f"{path}: write failed: {e}")

    return result


# ---------- rule: natural-systems-pre-reg-frontmatter (report-only) ----------


def apply_rule_natural_systems_pre_reg_frontmatter(project_root: Path, *, apply: bool) -> RuleResult:
    """Report-only: emit canonical-FM suggestions for NS pre-reg files missing ``id:`` / ``type:``.

    This rule never mutates files. It produces ``manual-suggested`` entries
    so the operator can review and apply manually (the missing fields
    ``committed:`` and ``spec:`` cannot be derived mechanically).
    """
    _ = apply  # report-only; never writes
    result = RuleResult(name="natural-systems-pre-reg-frontmatter")

    meta_dir = project_root / "doc" / "meta"
    if not meta_dir.is_dir():
        return result

    for path in sorted(meta_dir.glob("pre-registration-*.md")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            result.errors.append(f"{path}: read failed: {e}")
            continue
        split = _split_frontmatter(text)
        if split is None:
            # No frontmatter at all — also a gap, treat as missing both.
            current_fm = "(no frontmatter)"
            has_id = False
            has_type = False
        else:
            fm, _body = split
            current_fm = fm.rstrip("\n")
            has_id = _RE_FM_HAS_ID.search(fm) is not None
            has_type = _RE_FM_HAS_TYPE.search(fm) is not None
        if has_id and has_type:
            # Already declares both — nothing to suggest.
            continue

        slug = path.stem.removeprefix("pre-registration-")
        suggested_lines = [
            "---",
            f'id: "pre-registration:{slug}"',
            'type: "pre-registration"',
            "committed: <TODO>  # YYYY-MM-DD the pre-registration was committed",
            'spec: "<TODO>"     # back-link to the design spec or hypothesis file',
            "---",
        ]
        suggested_fm = "\n".join(suggested_lines)

        result.changes.append(
            FileChange(
                path=path,
                kind="manual-suggested",
                before=current_fm,
                after=suggested_fm,
                line_no=1,
            )
        )
        result.files_touched.add(path)

    return result


# ---------- rule: specs-frontmatter-backfill ----------

_RE_SPEC_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
_RE_SPEC_FIRST_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _yaml_double_quote(value: str) -> str:
    """Quote ``value`` for a YAML double-quoted scalar.

    Only ``\\`` and ``"`` need escaping in a double-quoted scalar; other
    printable characters (em-dash, colon, parens) are safe inside the
    quotes.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def apply_rule_specs_frontmatter_backfill(project_root: Path, *, apply: bool) -> RuleResult:
    """Add minimal canonical frontmatter to ``<project>/specs/*.md`` files."""
    result = RuleResult(name="specs-frontmatter-backfill")
    specs_dir = project_root / "specs"
    if not specs_dir.is_dir():
        return result

    for path in sorted(specs_dir.glob("*.md")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            result.errors.append(f"{path}: read failed: {e}")
            continue
        if text.startswith("---\n"):
            # Already has frontmatter — leave alone.
            continue

        basename = path.stem
        h1 = _RE_SPEC_FIRST_H1.search(text)
        title = h1.group(1).strip() if h1 else basename
        date_match = _RE_SPEC_DATE_PREFIX.match(basename)

        fm_lines = [
            "---",
            f'id: "spec:{basename}"',
            'type: "spec"',
            f"title: {_yaml_double_quote(title)}",
        ]
        if date_match:
            fm_lines.append(f"date: {date_match.group(1)}")
        fm_lines.append('status: "design"')
        fm_lines.append("---")
        fm_lines.append("")
        new_frontmatter = "\n".join(fm_lines) + "\n"
        new_text = new_frontmatter + text

        # Each backfill is a single logical change (add frontmatter block).
        # Record one line entry pointing at line 1 with a synthesized
        # before/after summary; the full block goes to disk on apply.
        result.changes.append(
            FileChange(
                path=path,
                kind="frontmatter-backfill",
                before="(no frontmatter)",
                after=f'id: "spec:{basename}"',
                line_no=1,
            )
        )
        result.files_touched.add(path)
        if apply:
            try:
                path.write_text(new_text, encoding="utf-8")
            except OSError as e:
                result.errors.append(f"{path}: write failed: {e}")

    return result


# ---------- rule: task-status-canonicalize ----------


_CANONICAL_TASK_STATUSES = frozenset({"active", "blocked", "deferred", "done", "proposed", "retired"})

# Map drifted values to their canonical equivalent. Unmapped non-canonical
# values (e.g. typos, novel drift shapes) are surfaced as errors rather than
# guessed at.
_TASK_STATUS_DRIFT_MAP = {
    "completed": "done",
    "complete": "done",
    "in-progress": "active",
    "in_progress": "active",
}

# Match a task-block status line. Tolerates both `- status: value` (the dominant
# shape in tasks/active.md and tasks/done/*.md) and bare `status: value` (the
# shape used inside frontmatter blocks). The leading dash form is the one we
# expect in task entries; `_in_task_block` gates application either way.
_RE_TASK_STATUS_LINE = re.compile(r'^(\s*-?\s*status:\s*)(["\']?)([A-Za-z][A-Za-z0-9_-]*)\2(\s*)$')

# Match a task-block header (`## [tNNN] Title` or `## [tNNN-slug] Title`).
_RE_TASK_BLOCK_HEADER = re.compile(r"^##\s+\[t[A-Za-z0-9_-]+\]")


def apply_rule_task_status_canonicalize(project_root: Path, *, apply: bool) -> RuleResult:
    """Normalize task ``status:`` values to the canonical set."""
    result = RuleResult(name="task-status-canonicalize")
    candidates: list[Path] = []
    active = project_root / "tasks" / "active.md"
    if active.is_file():
        candidates.append(active)
    done_dir = project_root / "tasks" / "done"
    if done_dir.is_dir():
        candidates.extend(sorted(p for p in done_dir.glob("*.md") if p.is_file()))

    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            result.errors.append(f"{path}: read failed: {e}")
            continue

        original_lines = text.splitlines(keepends=True)
        new_lines: list[str] = []
        in_task_block = False
        changed = False

        for line_no, line in enumerate(original_lines, start=1):
            if _RE_TASK_BLOCK_HEADER.match(line):
                in_task_block = True
                new_lines.append(line)
                continue
            if line.strip() == "" and in_task_block:
                # Blank line ends the metadata block within a task.
                in_task_block = False
                new_lines.append(line)
                continue
            if not in_task_block:
                new_lines.append(line)
                continue

            m = _RE_TASK_STATUS_LINE.match(line.rstrip("\n"))
            if not m:
                new_lines.append(line)
                continue

            prefix, quote, value, trailing = m.group(1), m.group(2), m.group(3), m.group(4)
            if value in _CANONICAL_TASK_STATUSES:
                new_lines.append(line)
                continue

            mapped = _TASK_STATUS_DRIFT_MAP.get(value)
            if mapped is None:
                result.errors.append(
                    f"{path}:{line_no}: unmapped non-canonical status {value!r}; "
                    "extend _TASK_STATUS_DRIFT_MAP before re-running."
                )
                new_lines.append(line)
                continue

            new_line_body = f"{prefix}{quote}{mapped}{quote}{trailing}"
            ending = "\n" if line.endswith("\n") else ""
            new_lines.append(new_line_body + ending)
            changed = True
            result.changes.append(
                FileChange(
                    path=path,
                    kind="task-status",
                    before=line.rstrip("\n").strip(),
                    after=new_line_body.strip(),
                    line_no=line_no,
                )
            )

        if changed:
            result.files_touched.add(path)
            if apply:
                try:
                    path.write_text("".join(new_lines), encoding="utf-8")
                except OSError as e:
                    result.errors.append(f"{path}: write failed: {e}")

    return result


# ---------- self-test ----------


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@local"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _git_commit_all(root: Path, msg: str = "init") -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", msg], cwd=root, check=True)


def _self_test_report_id_prefix(td: Path) -> None:
    """Cover the original report-id-prefix rule (kept unchanged)."""
    root = td / "rip-fixture"
    root.mkdir()
    _git_init(root)
    (root / "doc" / "reports" / "synthesis").mkdir(parents=True)
    (root / "doc" / "interpretations").mkdir()
    (root / "tasks").mkdir()

    drifted = root / "doc" / "reports" / "2026-04-25-foo.md"
    drifted.write_text(
        '---\nid: "doc:2026-04-25-foo"\ntype: "report"\n---\n\nbody\n',
        encoding="utf-8",
    )
    canon = root / "doc" / "reports" / "2026-04-25-bar.md"
    canon_text = '---\nid: "report:2026-04-25-bar"\ntype: "report"\n---\n\nbody\n'
    canon.write_text(canon_text, encoding="utf-8")
    synth = root / "doc" / "reports" / "synthesis" / "h01.md"
    synth_text = '---\nid: "synthesis:h01"\ntype: "synthesis"\n---\n\nbody\n'
    synth.write_text(synth_text, encoding="utf-8")
    interp = root / "doc" / "interpretations" / "2026-04-13-baz.md"
    interp_text = '---\nid: "interpretation:2026-04-13-baz"\ntype: "interpretation"\n---\n\nbody\n'
    interp.write_text(interp_text, encoding="utf-8")
    tasks = root / "tasks" / "active.md"
    tasks.write_text(
        "## [t100] sample\n"
        "- related: [doc:reports/2026-04-25-foo, doc:reports/synthesis,"
        " doc:reports/synthesis/_emergent-threads, doc:2026-04-25-foo,"
        " doc:2026-04-13-baz]\n"
        "\n"
        "File path `doc/reports/2026-04-25-foo.md` must NOT match.\n"
        "Inline mention `doc:reports/2026-04-25-foo` SHOULD match.\n"
        "Bare report mention `doc:2026-04-25-foo` SHOULD match.\n"
        "Bare interpretation mention `doc:2026-04-13-baz` must NOT match.\n",
        encoding="utf-8",
    )
    _git_commit_all(root)

    dry = apply_rule_report_id_prefix(root, apply=False)
    assert dry.errors == [], f"unexpected errors: {dry.errors}"
    kinds = [(c.path.name, c.kind) for c in dry.changes]
    assert ("2026-04-25-foo.md", "frontmatter-id") in kinds, kinds
    assert not any(p == "2026-04-25-bar.md" for p, _ in kinds), kinds
    mention_changes = [c for c in dry.changes if c.kind == "mention"]
    assert len(mention_changes) == 3, mention_changes

    wet = apply_rule_report_id_prefix(root, apply=True)
    assert wet.errors == [], wet.errors
    assert "report:2026-04-25-foo" in drifted.read_text()
    again = apply_rule_report_id_prefix(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _make_fixture(td: Path, name: str) -> Path:
    root = td / name
    root.mkdir()
    _git_init(root)
    (root / "doc" / "reports" / "synthesis").mkdir(parents=True)
    (root / "tasks").mkdir()
    return root


def _self_test_rollup_mm30(td: Path) -> None:
    """mm30 rollup shape: id: report:synthesis + type: report + report_kind already present."""
    root = _make_fixture(td, "rollup-mm30")
    rollup = root / "doc" / "reports" / "synthesis.md"
    rollup_orig = '---\nid: "report:synthesis"\ntype: "report"\nreport_kind: "synthesis-rollup"\n---\n\nrollup body\n'
    rollup.write_text(rollup_orig, encoding="utf-8")
    threads = root / "doc" / "reports" / "synthesis" / "_emergent-threads.md"
    threads.write_text(
        '---\ntype: "report"\nid: "report:synthesis-emergent-threads"\n'
        'report_kind: "emergent-threads"\n---\n\nthreads body\n',
        encoding="utf-8",
    )
    tasks = root / "tasks" / "active.md"
    tasks.write_text(
        "Refs: [report:synthesis, report:synthesis-h1-foo].\n",
        encoding="utf-8",
    )
    _git_commit_all(root)

    dry = apply_rule_synthesis_type_and_id_rollup(root, apply=False)
    assert dry.errors == [], dry.errors
    assert any(c.path == rollup for c in dry.changes), dry.changes
    # Mention rewrite expected on tasks file (literal report:synthesis).
    assert any(c.path == tasks and c.kind == "mention" for c in dry.changes), dry.changes
    # Dry-run wrote nothing.
    assert rollup.read_text() == rollup_orig

    wet = apply_rule_synthesis_type_and_id_rollup(root, apply=True)
    assert wet.errors == [], wet.errors
    after = rollup.read_text()
    assert 'type: "synthesis"' in after, after
    assert 'id: "synthesis:rollup"' in after, after
    assert 'report_kind: "synthesis-rollup"' in after, after
    # Mention pass: report:synthesis (literal) → synthesis:rollup, but
    # report:synthesis-h1-foo (per-hyp) preserved (different rule).
    ts = tasks.read_text()
    assert "synthesis:rollup" in ts, ts
    assert "report:synthesis-h1-foo" in ts, ts

    again = apply_rule_synthesis_type_and_id_rollup(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _self_test_rollup_pl(td: Path) -> None:
    """PL rollup shape: NO id + type: synthesis-rollup + NO report_kind + orphan_question_count."""
    root = _make_fixture(td, "rollup-pl")
    rollup = root / "doc" / "reports" / "synthesis.md"
    rollup_orig = (
        "---\n"
        'type: "synthesis-rollup"\n'
        'generated_at: "2026-04-25T00:00:00Z"\n'
        'source_commit: "abc123"\n'
        "synthesized_from:\n"
        '  - hypothesis: "hypothesis:h01-foo"\n'
        '    file: "doc/reports/synthesis/h01-foo.md"\n'
        '    sha: "deadbeef"\n'
        'emergent_threads_sha: "feedface"\n'
        "orphan_question_count: 23\n"
        "orphan_interpretation_count: 5\n"
        "---\n"
        "\nrollup body\n"
    )
    rollup.write_text(rollup_orig, encoding="utf-8")
    threads = root / "doc" / "reports" / "synthesis" / "_emergent-threads.md"
    threads_orig = (
        '---\ntype: "emergent-threads"\ngenerated_at: "2026-04-25T00:00:00Z"\norphan_ids: []\n---\n\nthreads body\n'
    )
    threads.write_text(threads_orig, encoding="utf-8")
    _git_commit_all(root)

    dry = apply_rule_synthesis_type_and_id_rollup(root, apply=False)
    assert dry.errors == [], dry.errors
    # Both rollup and threads should be touched (orphan-move).
    assert rollup in dry.files_touched, dry.files_touched
    assert threads in dry.files_touched, dry.files_touched
    # Dry-run wrote nothing.
    assert rollup.read_text() == rollup_orig
    assert threads.read_text() == threads_orig

    wet = apply_rule_synthesis_type_and_id_rollup(root, apply=True)
    assert wet.errors == [], wet.errors
    after_rollup = rollup.read_text()
    assert 'type: "synthesis"' in after_rollup, after_rollup
    assert 'id: "synthesis:rollup"' in after_rollup, after_rollup
    assert 'report_kind: "synthesis-rollup"' in after_rollup, after_rollup
    # Q1=C: orphan fields stripped from rollup, moved to threads.
    assert "orphan_question_count" not in after_rollup, after_rollup
    assert "orphan_interpretation_count" not in after_rollup, after_rollup
    # Surviving fields preserved.
    assert 'source_commit: "abc123"' in after_rollup
    assert "synthesized_from:" in after_rollup
    assert 'emergent_threads_sha: "feedface"' in after_rollup
    after_threads = threads.read_text()
    assert "orphan_question_count: 23" in after_threads, after_threads
    assert "orphan_interpretation_count: 5" in after_threads, after_threads
    # Existing orphan_ids preserved (already present on threads, not clobbered).
    assert "orphan_ids: []" in after_threads, after_threads

    again = apply_rule_synthesis_type_and_id_rollup(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _self_test_rollup_ns(td: Path) -> None:
    """NS rollup shape: id: report:project-synthesis + type: report + NO report_kind."""
    root = _make_fixture(td, "rollup-ns")
    rollup = root / "doc" / "reports" / "synthesis.md"
    rollup_orig = (
        "---\n"
        'id: "report:project-synthesis"\n'
        'type: "report"\n'
        "synthesized_from:\n"
        '  - hypothesis: "hypothesis:h01"\n'
        '    file: "doc/reports/synthesis/h01.md"\n'
        '    sha: "abc"\n'
        "---\n"
        "\nrollup body\n"
    )
    rollup.write_text(rollup_orig, encoding="utf-8")
    tasks = root / "tasks" / "active.md"
    tasks.write_text(
        "See report:project-synthesis for the rollup.\n",
        encoding="utf-8",
    )
    _git_commit_all(root)

    dry = apply_rule_synthesis_type_and_id_rollup(root, apply=False)
    assert dry.errors == [], dry.errors
    assert rollup in dry.files_touched, dry.files_touched
    assert tasks in dry.files_touched, dry.files_touched

    wet = apply_rule_synthesis_type_and_id_rollup(root, apply=True)
    assert wet.errors == [], wet.errors
    after = rollup.read_text()
    assert 'type: "synthesis"' in after, after
    assert 'id: "synthesis:rollup"' in after, after
    assert 'report_kind: "synthesis-rollup"' in after, after
    ts = tasks.read_text()
    assert "synthesis:rollup" in ts, ts
    assert "report:project-synthesis" not in ts, ts

    again = apply_rule_synthesis_type_and_id_rollup(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _self_test_threads_mm30(td: Path) -> None:
    """mm30 threads: id: report:synthesis-emergent-threads + type: report + report_kind already."""
    root = _make_fixture(td, "threads-mm30")
    threads = root / "doc" / "reports" / "synthesis" / "_emergent-threads.md"
    threads_orig = (
        "---\n"
        'id: "report:synthesis-emergent-threads"\n'
        'type: "report"\n'
        'report_kind: "emergent-threads"\n'
        "orphan_question_count: 0\n"
        "orphan_interpretation_count: 0\n"
        "orphan_ids: []\n"
        "---\nbody\n"
    )
    threads.write_text(threads_orig, encoding="utf-8")
    tasks = root / "tasks" / "active.md"
    tasks.write_text(
        "Refs: [report:synthesis-emergent-threads, report:synthesis-h1-foo].\n",
        encoding="utf-8",
    )
    _git_commit_all(root)

    dry = apply_rule_synthesis_type_and_id_emergent_threads(root, apply=False)
    assert dry.errors == [], dry.errors
    assert threads in dry.files_touched
    assert tasks in dry.files_touched

    wet = apply_rule_synthesis_type_and_id_emergent_threads(root, apply=True)
    assert wet.errors == [], wet.errors
    after = threads.read_text()
    assert 'type: "synthesis"' in after, after
    assert 'id: "synthesis:emergent-threads"' in after, after
    assert 'report_kind: "emergent-threads"' in after, after
    # Existing orphan-count fields preserved (rule 2 must NOT touch them).
    assert "orphan_question_count: 0" in after
    assert "orphan_interpretation_count: 0" in after
    assert "orphan_ids: []" in after
    ts = tasks.read_text()
    assert "synthesis:emergent-threads" in ts, ts
    # Per-hyp mention preserved (different rule's domain).
    assert "report:synthesis-h1-foo" in ts, ts
    assert "report:synthesis-emergent-threads" not in ts, ts

    again = apply_rule_synthesis_type_and_id_emergent_threads(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _self_test_threads_pl(td: Path) -> None:
    """PL threads: NO id + type: emergent-threads + NO report_kind + orphan_ids."""
    root = _make_fixture(td, "threads-pl")
    threads = root / "doc" / "reports" / "synthesis" / "_emergent-threads.md"
    threads_orig = (
        "---\n"
        'type: "emergent-threads"\n'
        'generated_at: "2026-04-25T11:45:34Z"\n'
        'source_commit: "abc"\n'
        "orphan_ids: []\n"
        "---\n"
        "\nbody\n"
    )
    threads.write_text(threads_orig, encoding="utf-8")
    _git_commit_all(root)

    dry = apply_rule_synthesis_type_and_id_emergent_threads(root, apply=False)
    assert dry.errors == [], dry.errors
    assert threads in dry.files_touched

    wet = apply_rule_synthesis_type_and_id_emergent_threads(root, apply=True)
    assert wet.errors == [], wet.errors
    after = threads.read_text()
    assert 'type: "synthesis"' in after, after
    assert 'id: "synthesis:emergent-threads"' in after, after
    assert 'report_kind: "emergent-threads"' in after, after
    # Existing fields preserved.
    assert 'generated_at: "2026-04-25T11:45:34Z"' in after
    assert "orphan_ids: []" in after

    again = apply_rule_synthesis_type_and_id_emergent_threads(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _self_test_threads_ns(td: Path) -> None:
    """NS threads: id: report:emergent-threads + type: report + NO report_kind."""
    root = _make_fixture(td, "threads-ns")
    threads = root / "doc" / "reports" / "synthesis" / "_emergent-threads.md"
    threads_orig = '---\nid: "report:emergent-threads"\ntype: "report"\norphan_ids: []\n---\nbody\n'
    threads.write_text(threads_orig, encoding="utf-8")
    tasks = root / "tasks" / "active.md"
    tasks.write_text(
        "See `report:emergent-threads` and report:emergent-threads, ok\n",
        encoding="utf-8",
    )
    _git_commit_all(root)

    dry = apply_rule_synthesis_type_and_id_emergent_threads(root, apply=False)
    assert dry.errors == [], dry.errors
    assert threads in dry.files_touched
    assert tasks in dry.files_touched

    wet = apply_rule_synthesis_type_and_id_emergent_threads(root, apply=True)
    assert wet.errors == [], wet.errors
    after = threads.read_text()
    assert 'type: "synthesis"' in after, after
    assert 'id: "synthesis:emergent-threads"' in after, after
    assert 'report_kind: "emergent-threads"' in after, after
    ts = tasks.read_text()
    assert "synthesis:emergent-threads" in ts, ts
    assert "report:emergent-threads" not in ts, ts

    again = apply_rule_synthesis_type_and_id_emergent_threads(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _self_test_per_hyp_mm30(td: Path) -> None:
    """mm30 per-hyp: id: report:synthesis-<slug> + type: report + report_kind already."""
    root = _make_fixture(td, "per-hyp-mm30")
    f = root / "doc" / "reports" / "synthesis" / "h1-foo.md"
    orig = (
        "---\n"
        'id: "report:synthesis-h1-foo"\n'
        'type: "report"\n'
        'report_kind: "hypothesis-synthesis"\n'
        'hypothesis: "hypothesis:h1-foo"\n'
        "---\nbody\n"
    )
    f.write_text(orig, encoding="utf-8")
    tasks = root / "tasks" / "active.md"
    tasks.write_text(
        "Refs: [report:synthesis-h1-foo, report:synthesis-unknown].\n"
        "Path `doc/reports/synthesis/h1-foo.md` must NOT match.\n",
        encoding="utf-8",
    )
    _git_commit_all(root)

    dry = apply_rule_synthesis_type_and_id_per_hyp(root, apply=False)
    assert dry.errors == [], dry.errors
    assert f in dry.files_touched
    assert tasks in dry.files_touched

    wet = apply_rule_synthesis_type_and_id_per_hyp(root, apply=True)
    assert wet.errors == [], wet.errors
    after = f.read_text()
    assert 'id: "synthesis:h1-foo"' in after, after
    assert 'type: "synthesis"' in after, after
    ts = tasks.read_text()
    assert "synthesis:h1-foo" in ts, ts
    assert "report:synthesis-h1-foo" not in ts, ts
    # Path-keyed: unknown synthesis slug preserved.
    assert "report:synthesis-unknown" in ts, ts
    # File path preserved.
    assert "doc/reports/synthesis/h1-foo.md" in ts, ts

    again = apply_rule_synthesis_type_and_id_per_hyp(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _self_test_per_hyp_pl(td: Path) -> None:
    """PL per-hyp: id: synthesis:<slug> + type: synthesis + NO report_kind."""
    root = _make_fixture(td, "per-hyp-pl")
    f = root / "doc" / "reports" / "synthesis" / "h01-foo.md"
    orig = '---\nid: "synthesis:h01-foo"\ntype: "synthesis"\nhypothesis: "hypothesis:h01-foo"\n---\nbody\n'
    f.write_text(orig, encoding="utf-8")
    _git_commit_all(root)

    dry = apply_rule_synthesis_type_and_id_per_hyp(root, apply=False)
    assert dry.errors == [], dry.errors
    assert f in dry.files_touched

    wet = apply_rule_synthesis_type_and_id_per_hyp(root, apply=True)
    assert wet.errors == [], wet.errors
    after = f.read_text()
    assert 'report_kind: "hypothesis-synthesis"' in after, after
    # Order: type → report_kind insertion is after type.
    assert after.index('type: "synthesis"') < after.index('report_kind: "hypothesis-synthesis"')

    again = apply_rule_synthesis_type_and_id_per_hyp(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _self_test_per_hyp_ns(td: Path) -> None:
    """NS per-hyp: id: synthesis:<slug> + type: synthesis + NO report_kind + non-h-prefixed names."""
    root = _make_fixture(td, "per-hyp-ns")
    files = [
        ("double-categorical-foo.md", "synthesis:h01-double-categorical-foo"),
        ("dynamical-invariant-bar.md", "synthesis:h04-dynamical-invariant-bar"),
        ("higher-order-topology.md", "synthesis:h03-higher-order-topology"),
    ]
    for fname, fid in files:
        p = root / "doc" / "reports" / "synthesis" / fname
        p.write_text(
            f'---\nid: "{fid}"\ntype: "synthesis"\n---\nbody\n',
            encoding="utf-8",
        )
    _git_commit_all(root)

    dry = apply_rule_synthesis_type_and_id_per_hyp(root, apply=False)
    assert dry.errors == [], dry.errors
    # All three files (no filename-prefix gating) should be touched.
    assert len(dry.files_touched) == 3, dry.files_touched

    wet = apply_rule_synthesis_type_and_id_per_hyp(root, apply=True)
    assert wet.errors == [], wet.errors
    for fname, _ in files:
        p = root / "doc" / "reports" / "synthesis" / fname
        after = p.read_text()
        # Id must be rewritten to match the file stem (this is the
        # canonical slug). NS's pre-existing ids embedded h-prefixes
        # that don't match the stem; rule rewrites to the stem.
        expected_stem = fname.removesuffix(".md")
        assert f'id: "synthesis:{expected_stem}"' in after, after
        assert 'report_kind: "hypothesis-synthesis"' in after, after

    again = apply_rule_synthesis_type_and_id_per_hyp(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _self_test_per_hyp_excludes_underscore(td: Path) -> None:
    """``_emergent-threads.md`` and other ``_*`` files are NOT touched by per-hyp rule."""
    root = _make_fixture(td, "per-hyp-exclude")
    threads = root / "doc" / "reports" / "synthesis" / "_emergent-threads.md"
    threads_orig = '---\nid: "report:emergent-threads"\ntype: "report"\n---\nbody\n'
    threads.write_text(threads_orig, encoding="utf-8")
    _git_commit_all(root)

    dry = apply_rule_synthesis_type_and_id_per_hyp(root, apply=False)
    assert dry.errors == [], dry.errors
    assert threads not in dry.files_touched, dry.files_touched
    assert threads.read_text() == threads_orig


def _self_test_pre_reg_canonical(td: Path) -> None:
    """Canonical id form: rewrite type only."""
    root = td / "pre-reg-canonical"
    root.mkdir()
    _git_init(root)
    (root / "doc" / "pre-registrations").mkdir(parents=True)
    (root / "doc" / "meta").mkdir(parents=True)
    (root / "tasks").mkdir()

    p = root / "doc" / "pre-registrations" / "2026-04-12-foo.md"
    orig = '---\nid: "pre-registration:2026-04-12-foo"\ntype: "plan"\ncommitted: 2026-04-12\n---\nbody\n'
    p.write_text(orig, encoding="utf-8")
    p_already = root / "doc" / "meta" / "pre-registration-already.md"
    p_already_orig = '---\nid: "pre-registration:already"\ntype: "pre-registration"\n---\nbody\n'
    p_already.write_text(p_already_orig, encoding="utf-8")
    _git_commit_all(root)

    dry = apply_rule_pre_registration_id_and_type(root, apply=False)
    assert dry.errors == [], dry.errors
    names = sorted(c.path.name for c in dry.changes)
    assert names == ["2026-04-12-foo.md"], names

    wet = apply_rule_pre_registration_id_and_type(root, apply=True)
    assert wet.errors == [], wet.errors
    assert 'type: "pre-registration"' in p.read_text()
    assert p_already.read_text() == p_already_orig
    again = apply_rule_pre_registration_id_and_type(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _self_test_pre_reg_ns_third_shape(td: Path) -> None:
    """NS third-shape id form: id: plan:pre-registration-<slug> + type: plan."""
    root = td / "pre-reg-ns"
    root.mkdir()
    _git_init(root)
    (root / "doc" / "meta").mkdir(parents=True)
    (root / "tasks").mkdir()

    p = root / "doc" / "meta" / "pre-registration-t214.md"
    orig = '---\nid: "plan:pre-registration-t214"\ntype: "plan"\nspec: "specs/something.md"\n---\nbody\n'
    p.write_text(orig, encoding="utf-8")
    tasks = root / "tasks" / "active.md"
    tasks.write_text(
        "See plan:pre-registration-t214 for details.\nUnknown: plan:pre-registration-other.\n",
        encoding="utf-8",
    )
    _git_commit_all(root)

    dry = apply_rule_pre_registration_id_and_type(root, apply=False)
    assert dry.errors == [], dry.errors
    assert p in dry.files_touched
    assert tasks in dry.files_touched

    wet = apply_rule_pre_registration_id_and_type(root, apply=True)
    assert wet.errors == [], wet.errors
    after = p.read_text()
    assert 'id: "pre-registration:t214"' in after, after
    assert 'type: "pre-registration"' in after, after
    # Existing field preserved.
    assert 'spec: "specs/something.md"' in after
    ts = tasks.read_text()
    assert "pre-registration:t214" in ts, ts
    assert "plan:pre-registration-t214" not in ts, ts
    # Path-keyed: unknown slug preserved.
    assert "plan:pre-registration-other" in ts, ts

    again = apply_rule_pre_registration_id_and_type(root, apply=True)
    assert again.changes == [], f"non-idempotent: {again.changes}"


def _self_test_pre_reg_skips_sparse(td: Path) -> None:
    """Sparse FM (no id:) is SKIPPED — handled by natural-systems rule."""
    root = td / "pre-reg-skip"
    root.mkdir()
    _git_init(root)
    (root / "doc" / "meta").mkdir(parents=True)
    p = root / "doc" / "meta" / "pre-registration-sparse.md"
    orig = "---\ntitle: 'Sparse'\n---\nbody\n"
    p.write_text(orig, encoding="utf-8")
    _git_commit_all(root)
    res = apply_rule_pre_registration_id_and_type(root, apply=True)
    assert res.changes == [], res.changes
    assert p.read_text() == orig


def _self_test_natural_systems_pre_reg_frontmatter(td: Path) -> None:
    """Report-only rule for sparse NS pre-reg files."""
    root = td / "ns-fm-fixture"
    root.mkdir()
    _git_init(root)
    (root / "doc" / "meta").mkdir(parents=True)

    n1 = root / "doc" / "meta" / "pre-registration-q54-temporal-profile.md"
    n1_orig = "---\ntitle: 'Pre-registration: Temporal Profile'\ncreated: '2026-03-30'\n---\n\nbody\n"
    n1.write_text(n1_orig, encoding="utf-8")
    n3 = root / "doc" / "meta" / "pre-registration-t214.md"
    n3_orig = '---\nid: "plan:pre-registration-t214"\ntype: "plan"\n---\nbody\n'
    n3.write_text(n3_orig, encoding="utf-8")

    dry = apply_rule_natural_systems_pre_reg_frontmatter(root, apply=False)
    assert dry.errors == [], dry.errors
    names = sorted(c.path.name for c in dry.changes)
    assert names == ["pre-registration-q54-temporal-profile.md"], names
    for c in dry.changes:
        assert "<TODO>" in c.after
        assert 'type: "pre-registration"' in c.after
    # apply=True must not write.
    apply_rule_natural_systems_pre_reg_frontmatter(root, apply=True)
    assert n1.read_text() == n1_orig
    assert n3.read_text() == n3_orig


def _self_test_specs_frontmatter_backfill(td: Path) -> None:
    """Specs backfill rule — kept unchanged."""
    root = td / "specs-fixture"
    root.mkdir()
    _git_init(root)
    (root / "specs").mkdir()
    spec_drift = root / "specs" / "2026-03-16-foo-design.md"
    spec_drift_orig = "# Foo Design\n\nBody.\n"
    spec_drift.write_text(spec_drift_orig, encoding="utf-8")
    _git_commit_all(root)
    res = apply_rule_specs_frontmatter_backfill(root, apply=True)
    assert res.errors == [], res.errors
    after = spec_drift.read_text()
    assert 'id: "spec:2026-03-16-foo-design"' in after
    assert 'title: "Foo Design"' in after
    again = apply_rule_specs_frontmatter_backfill(root, apply=True)
    assert again.changes == []


def _self_test_task_status_canonicalize(td: Path) -> None:
    """Exercise the task-status-canonicalize rule across drift shapes."""
    root = td / "task-status-fixture"
    root.mkdir()
    _git_init(root)
    (root / "tasks").mkdir()
    (root / "tasks" / "done").mkdir()

    active = root / "tasks" / "active.md"
    active_orig = (
        "# Active tasks\n"
        "\n"
        "## [t100] Drifted completed\n"
        "- priority: P1\n"
        "- status: completed\n"
        "- aspects: [hypothesis-testing]\n"
        "- created: 2026-04-25\n"
        "\n"
        "Body line.\n"
        "\n"
        "## [t101] Drifted in-progress\n"
        "- priority: P2\n"
        "- status: in-progress\n"
        "- created: 2026-04-25\n"
        "\n"
        "Body.\n"
        "\n"
        "## [t102] Drifted in_progress (underscore variant)\n"
        '- status: "in_progress"\n'
        "- priority: P2\n"
        "\n"
        "Body.\n"
        "\n"
        "## [t103] Already canonical\n"
        "- status: proposed\n"
        "- priority: P3\n"
        "\n"
        "Body.\n"
    )
    active.write_text(active_orig, encoding="utf-8")

    done = root / "tasks" / "done" / "2026-04.md"
    done_orig = (
        "## [t050] Drifted complete\n"
        "- priority: P1\n"
        "- status: complete\n"
        "- created: 2026-04-01\n"
        "\n"
        "Body.\n"
        "\n"
        "## [t051] Canonical done\n"
        "- status: done\n"
        "- priority: P2\n"
        "\n"
        "Body.\n"
    )
    done.write_text(done_orig, encoding="utf-8")

    # A non-task file with `status: completed` in frontmatter — must not be touched.
    (root / "doc" / "interpretations").mkdir(parents=True)
    interp = root / "doc" / "interpretations" / "x.md"
    interp_orig = '---\nid: "interpretation:x"\nstatus: "complete"\n---\n\nBody.\n'
    interp.write_text(interp_orig, encoding="utf-8")

    _git_commit_all(root)

    # Dry run — count and shape of changes.
    dry = apply_rule_task_status_canonicalize(root, apply=False)
    assert dry.errors == [], dry.errors
    assert {c.path for c in dry.changes} == {active, done}, [c.path for c in dry.changes]
    by_line = {(c.path.name, c.line_no): (c.before, c.after) for c in dry.changes}
    # active.md: t100 (line 5), t101 (line 13), t102 (line 19). t103 unchanged.
    assert by_line[("active.md", 5)][0].endswith("completed")
    assert by_line[("active.md", 5)][1].endswith("done")
    assert by_line[("active.md", 13)][0].endswith("in-progress")
    assert by_line[("active.md", 13)][1].endswith("active")
    assert "in_progress" in by_line[("active.md", 19)][0]
    assert by_line[("active.md", 19)][1].endswith('"active"'), by_line[("active.md", 19)][1]
    # done file: t050 (line 3) `complete` → `done`. t051 unchanged.
    assert by_line[("2026-04.md", 3)][0].endswith("complete")
    assert by_line[("2026-04.md", 3)][1].endswith("done")
    # Non-task file untouched.
    assert active.read_text() == active_orig
    assert done.read_text() == done_orig
    assert interp.read_text() == interp_orig

    # Apply.
    res = apply_rule_task_status_canonicalize(root, apply=True)
    assert res.errors == [], res.errors
    after_active = active.read_text()
    assert "- status: done\n" in after_active
    assert "- status: active\n" in after_active
    assert '- status: "active"\n' in after_active  # quoted variant preserved
    # No status line should still carry a drift value. Title text on `## [t...]`
    # lines is allowed to contain the word "completed" / "in-progress".
    status_lines = [ln for ln in after_active.splitlines() if "status:" in ln and not ln.startswith("##")]
    assert all("completed" not in ln for ln in status_lines), status_lines
    assert all("in-progress" not in ln for ln in status_lines), status_lines
    assert all("in_progress" not in ln for ln in status_lines), status_lines
    after_done = done.read_text()
    assert "- status: done\n" in after_done
    done_status_lines = [ln for ln in after_done.splitlines() if "status:" in ln and not ln.startswith("##")]
    assert all("complete" not in ln for ln in done_status_lines), done_status_lines
    # Idempotent.
    again = apply_rule_task_status_canonicalize(root, apply=True)
    assert again.changes == [], again.changes
    # Non-task file still untouched.
    assert interp.read_text() == interp_orig

    # Unmapped drift surfaces as an error.
    weird = root / "tasks" / "active.md"
    weird.write_text(
        "## [t999] Weird status\n- status: started\n- priority: P3\n\nBody.\n",
        encoding="utf-8",
    )
    bad = apply_rule_task_status_canonicalize(root, apply=False)
    assert any("unmapped non-canonical status 'started'" in e for e in bad.errors), bad.errors


def _self_test() -> None:
    """Exercise all rules against tempdir fixtures and assert expected outcomes."""
    with tempfile.TemporaryDirectory() as tdname:
        td = Path(tdname)
        # Original / kept rules.
        _self_test_report_id_prefix(td)
        _self_test_specs_frontmatter_backfill(td)
        _self_test_natural_systems_pre_reg_frontmatter(td)
        _self_test_task_status_canonicalize(td)

        # Rule 1: synthesis-type-and-id-rollup — 3 fixtures (mm30, PL, NS).
        _self_test_rollup_mm30(td)
        _self_test_rollup_pl(td)
        _self_test_rollup_ns(td)

        # Rule 2: synthesis-type-and-id-emergent-threads — 3 fixtures.
        _self_test_threads_mm30(td)
        _self_test_threads_pl(td)
        _self_test_threads_ns(td)

        # Rule 3: synthesis-type-and-id-per-hyp — 3 fixtures + scope check.
        _self_test_per_hyp_mm30(td)
        _self_test_per_hyp_pl(td)
        _self_test_per_hyp_ns(td)
        _self_test_per_hyp_excludes_underscore(td)

        # Rule 4: pre-registration-id-and-type — 3 fixtures.
        _self_test_pre_reg_canonical(td)
        _self_test_pre_reg_ns_third_shape(td)
        _self_test_pre_reg_skips_sparse(td)

        click.echo("self-test: PASS")


# ---------- CLI ----------


RULES = {
    "report-id-prefix": apply_rule_report_id_prefix,
    "synthesis-type-and-id-rollup": apply_rule_synthesis_type_and_id_rollup,
    "synthesis-type-and-id-emergent-threads": apply_rule_synthesis_type_and_id_emergent_threads,
    "synthesis-type-and-id-per-hyp": apply_rule_synthesis_type_and_id_per_hyp,
    "pre-registration-id-and-type": apply_rule_pre_registration_id_and_type,
    "natural-systems-pre-reg-frontmatter": apply_rule_natural_systems_pre_reg_frontmatter,
    "specs-frontmatter-backfill": apply_rule_specs_frontmatter_backfill,
    "task-status-canonicalize": apply_rule_task_status_canonicalize,
}


@click.command()
@click.argument(
    "project_root",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=False,
)
@click.option(
    "--rule",
    type=click.Choice(sorted(RULES.keys())),
    default=None,
    help="Migration rule to run.",
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    default=False,
    help="Write changes. Without this, runs in dry-run mode.",
)
@click.option(
    "--self-test",
    is_flag=True,
    default=False,
    help="Run internal sanity checks against a tempdir fixture and exit.",
)
def main(
    project_root: Path | None,
    rule: str | None,
    apply_changes: bool,
    self_test: bool,
) -> None:
    """Apply downstream-project convention migrations."""
    if self_test:
        _self_test()
        return
    if project_root is None:
        raise click.UsageError("PROJECT_ROOT is required unless --self-test is given.")
    if rule is None:
        raise click.UsageError("--rule is required (choose one: " + ", ".join(sorted(RULES)) + ")")
    project_root = project_root.resolve()
    res = RULES[rule](project_root, apply=apply_changes)

    mode = "APPLIED" if apply_changes else "DRY-RUN"
    click.echo(f"== {res.name}: {mode} ==")
    click.echo(f"project: {project_root}")
    click.echo(f"files touched: {len(res.files_touched)}")
    click.echo(f"changes: {len(res.changes)}")
    for c in res.changes:
        click.echo(c.render(base=project_root))
    if res.errors:
        click.echo("\nERRORS:")
        for e in res.errors:
            click.echo(f"  {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
