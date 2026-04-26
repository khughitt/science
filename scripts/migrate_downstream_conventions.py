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

- ``synthesis-type-mm30``: Migrate mm30-shape synthesis files from
  ``type: "report"`` to ``type: "synthesis"`` and rewrite their ids
  from ``report:synthesis-<slug>`` → ``synthesis:<slug>`` (per-hypothesis
  files under ``<project>/doc/reports/synthesis/*.md``) and the literal
  ``report:synthesis`` → ``synthesis:rollup`` (the rollup file
  ``<project>/doc/reports/synthesis.md``). Pass 2 rewrites entity-ref
  mentions of the same shapes across all tracked markdown. Per audit
  synthesis §3.3 — mm30 ships the canonical structured-rollup shape
  but with a divergent ``type:`` value; Plan #4 promoted ``synthesis``
  as the canonical type.

- ``synthesis-type-pl-emergent-threads``: Migrate
  ``<project>/doc/reports/synthesis/_emergent-threads.md`` from
  ``type: "emergent-threads"`` to ``type: "synthesis"`` and insert
  ``id: "synthesis:emergent-threads"`` plus ``report_kind:
  "emergent-threads"`` immediately after the new ``type:`` line. Other
  fields (counts, orphan ids, provenance) are unchanged. Per audit
  synthesis §3.3 / Plan #4. Single-file rule; idempotent if the file
  already declares the canonical shape.

- ``synthesis-report-kind-pl-hyp``: For per-hypothesis synthesis files
  ``<project>/doc/reports/synthesis/h*.md`` that already declare
  ``type: "synthesis"`` but lack ``report_kind:``, insert
  ``report_kind: "hypothesis-synthesis"`` immediately after the
  ``type:`` line. No-op if ``report_kind:`` is already present. Per
  audit synthesis §3.3 / Plan #4.

- ``pre-registration-type``: Migrate pre-registration files from
  ``type: "plan"`` to ``type: "pre-registration"`` for files matching
  ``<project>/doc/meta/pre-registration-*.md`` or
  ``<project>/doc/pre-registrations/*.md`` whose frontmatter ``id:``
  starts with ``pre-registration:``. Files with a different id prefix
  (e.g. ``id: "plan:pre-registration-<slug>"``) are NOT rewritten by
  this rule; those need a separate id rewrite (see
  ``natural-systems-pre-reg-frontmatter``). Per audit synthesis §3.2 /
  Plan #2.

- ``natural-systems-pre-reg-frontmatter``: REPORT-ONLY rule (does NOT
  mutate). For files matching ``<project>/doc/meta/pre-registration-*.md``
  whose frontmatter is missing ``id:`` and/or ``type:``, emit a
  per-file canonical-frontmatter suggestion with ``<TODO>``
  placeholders for fields that cannot be derived mechanically
  (``committed:``, ``spec:``). Operator reviews and applies manually.
  Per audit synthesis §3.2 — natural-systems' three sparser pre-reg
  files need human input on these fields.

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


# ---------- rule 1: report-id-prefix ----------

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
_RE_REPORT_ID_MENTION = re.compile(
    rf"(?<![A-Za-z0-9_./-])doc:reports/({_DATE_SLUG})(?![A-Za-z0-9_./-])"
)

# Match bare ``doc:DATE-slug`` entity-ref mentions (no ``reports/`` infix).
# Path-keyed against the reports directory at substitution time so this only
# rewrites refs that resolve to a known report file.
_RE_REPORT_ID_BARE_MENTION = re.compile(
    rf"(?<![A-Za-z0-9_./-])doc:({_DATE_SLUG})(?![A-Za-z0-9_./-])"
)


@dataclass
class FileChange:
    path: Path
    kind: str  # "frontmatter-id" | "mention"
    before: str
    after: str
    line_no: int

    def render(self, base: Path | None = None) -> str:
        p = self.path.relative_to(base) if base else self.path
        return (
            f"  {p}:{self.line_no}  [{self.kind}]\n"
            f"    - {self.before}\n"
            f"    + {self.after}"
        )


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
        return sorted(
            p
            for p in project_root.rglob("*.md")
            if not (set(p.relative_to(project_root).parts) & excluded)
        )


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
    for i, (a, b) in enumerate(
        zip(before_text.splitlines(), after_text.splitlines()), start=1 + line_offset
    ):
        if a != b:
            result.changes.append(
                FileChange(
                    path=path, kind=kind, before=a.strip(), after=b.strip(), line_no=i
                )
            )


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


# ---------- rule: synthesis-type-mm30 ----------

# Per-hypothesis synthesis slug regex. Per-hyp slugs are NOT date-prefixed
# (e.g. ``h1-foo``, ``h01-bar``) so we use a permissive identifier regex.
_SYNTH_SLUG = r"[A-Za-z0-9_-]+"

# Frontmatter rewrites for mm30-shape synthesis files.
_RE_SYNTH_TYPE_REPORT = re.compile(
    r'^(type:\s*)(["\']?)report\2(\s*)$',
    re.MULTILINE,
)
_RE_SYNTH_ID_PER_HYP = re.compile(
    rf'^(id:\s*)(["\']?)report:synthesis-({_SYNTH_SLUG})\2(\s*)$',
    re.MULTILINE,
)
_RE_SYNTH_ID_ROLLUP = re.compile(
    r'^(id:\s*)(["\']?)report:synthesis\2(\s*)$',
    re.MULTILINE,
)

# Mention-side rewrites. Match ``report:synthesis-<slug>`` followed by
# anything that is not part of the slug character class. Path-keyed against
# known synthesis stems at substitution time so we never rewrite mentions
# of slugs that aren't real synthesis files.
_RE_SYNTH_MENTION_PER_HYP = re.compile(
    rf"(?<![A-Za-z0-9_./-])report:synthesis-({_SYNTH_SLUG})(?![A-Za-z0-9_./-])"
)
# Match the literal ``report:synthesis`` (no trailing slug) → ``synthesis:rollup``.
# Negative lookahead on ``-`` so it doesn't bite ``report:synthesis-h1`` mentions
# (those are handled by the per-hyp regex above).
_RE_SYNTH_MENTION_ROLLUP = re.compile(
    r"(?<![A-Za-z0-9_./-])report:synthesis(?![A-Za-z0-9_./:-])"
)


def apply_rule_synthesis_type_mm30(project_root: Path, *, apply: bool) -> RuleResult:
    """Migrate mm30-shape synthesis frontmatter + mentions to canonical ``synthesis:``."""
    result = RuleResult(name="synthesis-type-mm30")
    synth_dir = project_root / "doc" / "reports" / "synthesis"
    rollup_path = project_root / "doc" / "reports" / "synthesis.md"

    pass1_content: dict[Path, str] = {}

    def _rewrite_fm(path: Path, *, is_rollup: bool) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            result.errors.append(f"{path}: read failed: {e}")
            return
        split = _split_frontmatter(text)
        if split is None:
            return
        fm, body = split
        new_fm = fm
        # Rewrite ``type: "report"`` → ``type: "synthesis"``.
        new_fm, n_type = _RE_SYNTH_TYPE_REPORT.subn(r"\1\2synthesis\2\3", new_fm)
        # Id rewrites: rollup form first (only on the rollup file), then per-hyp form.
        n_id = 0
        if is_rollup:
            new_fm, n_id_r = _RE_SYNTH_ID_ROLLUP.subn(
                r"\1\2synthesis:rollup\2\3", new_fm
            )
            n_id += n_id_r
        new_fm, n_id_h = _RE_SYNTH_ID_PER_HYP.subn(r"\1\2synthesis:\3\2\4", new_fm)
        n_id += n_id_h
        if n_type == 0 and n_id == 0:
            return
        _record_line_changes(result, path, "frontmatter-id", fm, new_fm)
        result.files_touched.add(path)
        new_content = new_fm + body
        pass1_content[path] = new_content
        if apply:
            try:
                path.write_text(new_content, encoding="utf-8")
            except OSError as e:
                result.errors.append(f"{path}: write failed: {e}")

    # Pass 1a: rollup file (``doc/reports/synthesis.md``).
    if rollup_path.is_file():
        _rewrite_fm(rollup_path, is_rollup=True)
    # Pass 1b: per-hypothesis files (``doc/reports/synthesis/*.md``), excluding
    # files whose stem starts with ``_`` (those belong to other rules, e.g.
    # ``_emergent-threads``).
    if synth_dir.is_dir():
        for path in sorted(synth_dir.glob("*.md")):
            if not path.is_file() or path.stem.startswith("_"):
                continue
            _rewrite_fm(path, is_rollup=False)

    # Build per-hyp synthesis stem set for path-keyed mention rewrite.
    synth_stems: set[str] = set()
    if synth_dir.is_dir():
        synth_stems = {
            p.stem
            for p in synth_dir.glob("*.md")
            if p.is_file() and not p.stem.startswith("_")
        }

    def _rewrite_per_hyp_mention(match: re.Match[str]) -> str:
        slug = match.group(1)
        # ``report:synthesis-<slug>`` mention. The original id form was
        # ``report:synthesis-<stem>``; the canonical mention form is
        # ``synthesis:<stem>``. Path-keyed so we don't rewrite slugs that
        # aren't real synthesis files.
        if slug in synth_stems:
            return f"synthesis:{slug}"
        # Also accept slugs whose stem includes the leading ``synthesis-``
        # prefix already stripped — e.g. mention ``report:synthesis-foo`` when
        # the file stem is ``foo``. (Not the case for mm30; defensive only.)
        return match.group(0)

    # Pass 2: mention rewrites across all tracked markdown.
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
        new_text = _RE_SYNTH_MENTION_PER_HYP.sub(_rewrite_per_hyp_mention, text)
        new_text = _RE_SYNTH_MENTION_ROLLUP.sub("synthesis:rollup", new_text)
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


# ---------- rule: synthesis-type-pl-emergent-threads ----------

_RE_PL_EMERGENT_TYPE = re.compile(
    r'^(type:\s*)(["\']?)emergent-threads\2(\s*)$',
    re.MULTILINE,
)
_RE_PL_FM_HAS_ID = re.compile(r"^id:\s*", re.MULTILINE)
_RE_PL_FM_HAS_REPORT_KIND = re.compile(r"^report_kind:\s*", re.MULTILINE)


def apply_rule_synthesis_type_pl_emergent_threads(
    project_root: Path, *, apply: bool
) -> RuleResult:
    """Promote PL ``_emergent-threads.md`` to canonical ``type: synthesis`` + ``report_kind``."""
    result = RuleResult(name="synthesis-type-pl-emergent-threads")
    path = project_root / "doc" / "reports" / "synthesis" / "_emergent-threads.md"
    if not path.is_file():
        return result
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        result.errors.append(f"{path}: read failed: {e}")
        return result
    split = _split_frontmatter(text)
    if split is None:
        return result
    fm, body = split

    # Idempotence: if the file already declares the canonical shape we leave it alone.
    has_id = _RE_PL_FM_HAS_ID.search(fm) is not None
    has_report_kind = _RE_PL_FM_HAS_REPORT_KIND.search(fm) is not None
    if not _RE_PL_EMERGENT_TYPE.search(fm) and has_id and has_report_kind:
        return result

    new_fm, n = _RE_PL_EMERGENT_TYPE.subn(r"\1\2synthesis\2\3", fm)
    if n == 0:
        # type already migrated; still need to backfill id / report_kind if missing.
        new_fm = fm

    # Insert ``id:`` and ``report_kind:`` immediately after the (new) ``type:`` line,
    # but only the ones not already present.
    insertions: list[str] = []
    if not has_id:
        insertions.append('id: "synthesis:emergent-threads"')
    if not has_report_kind:
        insertions.append('report_kind: "emergent-threads"')

    if insertions:
        # Find the ``type: "synthesis"`` line (post-rewrite) and insert after it.
        type_line_re = re.compile(r'^(type:\s*["\']?synthesis["\']?\s*)$', re.MULTILINE)
        m = type_line_re.search(new_fm)
        if m is None:
            result.errors.append(f"{path}: could not locate type: line for insertion")
            return result
        insert_at = m.end()
        new_fm = new_fm[:insert_at] + "\n" + "\n".join(insertions) + new_fm[insert_at:]

    if new_fm == fm:
        return result

    _record_line_changes(result, path, "frontmatter-id", fm, new_fm)
    result.files_touched.add(path)
    if apply:
        try:
            path.write_text(new_fm + body, encoding="utf-8")
        except OSError as e:
            result.errors.append(f"{path}: write failed: {e}")

    return result


# ---------- rule: synthesis-report-kind-pl-hyp ----------

_RE_PL_HYP_TYPE_SYNTHESIS = re.compile(
    r'^(type:\s*["\']?synthesis["\']?\s*)$',
    re.MULTILINE,
)


def apply_rule_synthesis_report_kind_pl_hyp(
    project_root: Path, *, apply: bool
) -> RuleResult:
    """Insert ``report_kind: hypothesis-synthesis`` for PL per-hypothesis files lacking it."""
    result = RuleResult(name="synthesis-report-kind-pl-hyp")
    synth_dir = project_root / "doc" / "reports" / "synthesis"
    if not synth_dir.is_dir():
        return result

    for path in sorted(synth_dir.glob("h*.md")):
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
        # Skip files that don't declare ``type: synthesis`` — those need rule
        # ``synthesis-type-mm30`` first.
        m = _RE_PL_HYP_TYPE_SYNTHESIS.search(fm)
        if m is None:
            continue
        # Idempotence: skip if ``report_kind:`` already present.
        if _RE_PL_FM_HAS_REPORT_KIND.search(fm) is not None:
            continue
        insert_at = m.end()
        new_fm = (
            fm[:insert_at] + '\nreport_kind: "hypothesis-synthesis"' + fm[insert_at:]
        )
        _record_line_changes(result, path, "frontmatter-id", fm, new_fm)
        result.files_touched.add(path)
        if apply:
            try:
                path.write_text(new_fm + body, encoding="utf-8")
            except OSError as e:
                result.errors.append(f"{path}: write failed: {e}")

    return result


# ---------- rule: pre-registration-type ----------

_RE_PREREG_TYPE_PLAN = re.compile(
    r'^(type:\s*)(["\']?)plan\2(\s*)$',
    re.MULTILINE,
)
_RE_PREREG_ID_CANONICAL = re.compile(
    r'^id:\s*["\']?pre-registration:',
    re.MULTILINE,
)


def apply_rule_pre_registration_type(project_root: Path, *, apply: bool) -> RuleResult:
    """Migrate ``type: plan`` → ``type: pre-registration`` for canonical-id pre-reg files."""
    result = RuleResult(name="pre-registration-type")

    candidates: list[Path] = []
    meta_dir = project_root / "doc" / "meta"
    if meta_dir.is_dir():
        candidates.extend(sorted(meta_dir.glob("pre-registration-*.md")))
    pre_dir = project_root / "doc" / "pre-registrations"
    if pre_dir.is_dir():
        candidates.extend(sorted(pre_dir.glob("*.md")))

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
        # Only rewrite files with both ``type: "plan"`` AND ``id: "pre-registration:..."``.
        if _RE_PREREG_ID_CANONICAL.search(fm) is None:
            continue
        new_fm, n = _RE_PREREG_TYPE_PLAN.subn(r"\1\2pre-registration\2\3", fm)
        if n == 0:
            continue
        _record_line_changes(result, path, "frontmatter-id", fm, new_fm)
        result.files_touched.add(path)
        if apply:
            try:
                path.write_text(new_fm + body, encoding="utf-8")
            except OSError as e:
                result.errors.append(f"{path}: write failed: {e}")

    return result


# ---------- rule: natural-systems-pre-reg-frontmatter (report-only) ----------

_RE_PREREG_FM_HAS_TYPE = re.compile(r"^type:\s*", re.MULTILINE)


def apply_rule_natural_systems_pre_reg_frontmatter(
    project_root: Path, *, apply: bool
) -> RuleResult:
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
            has_id = _RE_PL_FM_HAS_ID.search(fm) is not None
            has_type = _RE_PREREG_FM_HAS_TYPE.search(fm) is not None
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


# ---------- rule 2: specs-frontmatter-backfill ----------

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


def apply_rule_specs_frontmatter_backfill(
    project_root: Path, *, apply: bool
) -> RuleResult:
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


# ---------- self-test ----------


def _self_test() -> None:
    """Exercise the rules against a tempdir fixture and assert expected outcomes."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "t@local"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
        (root / "doc" / "reports" / "synthesis").mkdir(parents=True)
        (root / "doc" / "interpretations").mkdir()
        (root / "tasks").mkdir()

        # (a) drifted report — frontmatter id should be migrated
        drifted = root / "doc" / "reports" / "2026-04-25-foo.md"
        drifted.write_text(
            '---\nid: "doc:2026-04-25-foo"\ntype: "report"\n---\n\nbody\n',
            encoding="utf-8",
        )
        # (b) already-canonical report — left alone
        canon = root / "doc" / "reports" / "2026-04-25-bar.md"
        canon_text = '---\nid: "report:2026-04-25-bar"\ntype: "report"\n---\n\nbody\n'
        canon.write_text(canon_text, encoding="utf-8")
        # (c) synthesis subdir file — outside rule 1 scope
        synth = root / "doc" / "reports" / "synthesis" / "h01.md"
        synth_text = '---\nid: "synthesis:h01"\ntype: "synthesis"\n---\n\nbody\n'
        synth.write_text(synth_text, encoding="utf-8")
        # (d) sibling interpretation file (its slug must NOT be rewritten when
        #     mentioned as `doc:DATE-slug` since it is not a report).
        interp = root / "doc" / "interpretations" / "2026-04-13-baz.md"
        interp_text = '---\nid: "interpretation:2026-04-13-baz"\ntype: "interpretation"\n---\n\nbody\n'
        interp.write_text(interp_text, encoding="utf-8")
        # (e) tasks file with mixed mentions:
        #   - infix-form mention of a report slug (rewritten)
        #   - directory-style infix mention (preserved)
        #   - synthesis subref (preserved)
        #   - file-path mention (preserved)
        #   - bare doc:DATE-slug for a *report* (rewritten)
        #   - bare doc:DATE-slug for an *interpretation* (preserved)
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
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)

        # Dry-run: report changes but write nothing.
        dry = apply_rule_report_id_prefix(root, apply=False)
        assert dry.errors == [], f"unexpected errors: {dry.errors}"
        kinds = [(c.path.name, c.kind) for c in dry.changes]
        assert ("2026-04-25-foo.md", "frontmatter-id") in kinds, kinds
        assert not any(p == "2026-04-25-bar.md" for p, _ in kinds), kinds
        assert not any(p == "h01.md" for p, _ in kinds), kinds
        assert not any(p == "2026-04-13-baz.md" for p, _ in kinds), kinds
        mention_changes = [c for c in dry.changes if c.kind == "mention"]
        # Expected mention rewrites in tasks/active.md:
        # line 2: `[doc:reports/2026-04-25-foo, ..., doc:2026-04-25-foo, ...]`
        # line 5: ``doc:reports/2026-04-25-foo``
        # line 6: ``doc:2026-04-25-foo``
        assert len(mention_changes) == 3, (
            f"expected 3 mention rewrites, got {mention_changes}"
        )
        # Files unchanged after dry-run
        assert "doc:2026-04-25-foo" in drifted.read_text(), "dry-run must not write"
        assert canon.read_text() == canon_text
        assert synth.read_text() == synth_text
        assert interp.read_text() == interp_text

        # Apply
        wet = apply_rule_report_id_prefix(root, apply=True)
        assert wet.errors == [], f"errors: {wet.errors}"
        assert "report:2026-04-25-foo" in drifted.read_text()
        assert "doc:2026-04-25-foo" not in drifted.read_text()
        ts = tasks.read_text()
        assert "report:2026-04-25-foo" in ts
        assert "doc:reports/2026-04-25-foo" not in ts, (
            "infix-form mention must be rewritten"
        )
        assert "doc:reports/synthesis" in ts, "directory ref must survive"
        assert "doc:reports/synthesis/_emergent-threads" in ts, (
            "synthesis subref must survive"
        )
        assert "doc/reports/2026-04-25-foo.md" in ts, "file-path mention must survive"
        assert "doc:2026-04-13-baz" in ts, "bare interpretation mention must survive"
        # Bare report mention: every `doc:2026-04-25-foo` (no `reports/` infix)
        # should now read `report:2026-04-25-foo`.
        assert ts.count("doc:2026-04-25-foo") == 0, (
            "bare report mentions must be rewritten"
        )
        assert ts.count("report:2026-04-25-foo") >= 3, (
            "expected 3 occurrences after rewrite"
        )
        assert canon.read_text() == canon_text, "canonical report must be untouched"
        assert synth.read_text() == synth_text, "synthesis file must be untouched"
        assert interp.read_text() == interp_text, "interpretation must be untouched"

        # Idempotence
        again = apply_rule_report_id_prefix(root, apply=True)
        assert again.changes == [], f"non-idempotent: {again.changes}"

        # ---- rule: synthesis-type-mm30 ----

        synth_root = Path(td) / "mm30-fixture"
        synth_root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=synth_root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "t@local"], cwd=synth_root, check=True
        )
        subprocess.run(["git", "config", "user.name", "t"], cwd=synth_root, check=True)
        (synth_root / "doc" / "reports" / "synthesis").mkdir(parents=True)
        (synth_root / "tasks").mkdir()

        # (sm1) per-hyp file with drifted type/id
        per_hyp = synth_root / "doc" / "reports" / "synthesis" / "h1-foo.md"
        per_hyp_orig = (
            "---\n"
            'id: "report:synthesis-h1-foo"\n'
            'type: "report"\n'
            'report_kind: "hypothesis-synthesis"\n'
            'hypothesis: "hypothesis:h1-foo"\n'
            "---\n"
            "\nbody\n"
        )
        per_hyp.write_text(per_hyp_orig, encoding="utf-8")
        # (sm2) rollup file with literal ``report:synthesis`` id
        rollup = synth_root / "doc" / "reports" / "synthesis.md"
        rollup_orig = (
            "---\n"
            'id: "report:synthesis"\n'
            'type: "report"\n'
            'report_kind: "synthesis-rollup"\n'
            "---\n"
            "\nrollup body\n"
        )
        rollup.write_text(rollup_orig, encoding="utf-8")
        # (sm3) emergent-threads file in the synthesis dir — must NOT be touched
        # by this rule (its stem starts with ``_``).
        threads = synth_root / "doc" / "reports" / "synthesis" / "_emergent-threads.md"
        threads_orig = '---\ntype: "emergent-threads"\n---\n\nthreads\n'
        threads.write_text(threads_orig, encoding="utf-8")
        # (sm4) tasks file with mixed mentions:
        #   - ``report:synthesis-h1-foo`` (per-hyp mention; rewritten)
        #   - ``report:synthesis`` (rollup mention; rewritten)
        #   - ``report:synthesis-unknown`` (unknown stem; preserved)
        #   - file-path mention ``doc/reports/synthesis/h1-foo.md`` (preserved)
        synth_tasks = synth_root / "tasks" / "active.md"
        synth_tasks.write_text(
            "## [t1] sample\n"
            "- refs: [report:synthesis-h1-foo, report:synthesis,"
            " report:synthesis-unknown]\n"
            "\n"
            "Path `doc/reports/synthesis/h1-foo.md` must NOT match.\n"
            "Inline `report:synthesis-h1-foo` SHOULD match.\n"
            "Inline `report:synthesis` SHOULD match.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=synth_root, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=synth_root, check=True)

        dry_synth = apply_rule_synthesis_type_mm30(synth_root, apply=False)
        assert dry_synth.errors == [], dry_synth.errors
        kinds_synth = [(c.path.name, c.kind) for c in dry_synth.changes]
        assert ("h1-foo.md", "frontmatter-id") in kinds_synth, kinds_synth
        assert ("synthesis.md", "frontmatter-id") in kinds_synth, kinds_synth
        # _emergent-threads.md is out of scope for this rule.
        assert not any(p == "_emergent-threads.md" for p, _ in kinds_synth), kinds_synth
        # Mention rewrites in tasks file recorded as line-level diffs:
        #   line 2: refs: [...] (per-hyp + rollup rewrites collapsed onto one line)
        #   line 5: per-hyp inline mention
        #   line 6: rollup inline mention
        # = 3 distinct line changes.
        synth_mention_changes = [c for c in dry_synth.changes if c.kind == "mention"]
        assert len(synth_mention_changes) == 3, synth_mention_changes
        # Spot-check line 2 carries BOTH rewrites
        line2 = next(c for c in synth_mention_changes if c.line_no == 2)
        assert (
            "synthesis:h1-foo" in line2.after and "synthesis:rollup" in line2.after
        ), line2
        # Dry-run did not write
        assert per_hyp.read_text() == per_hyp_orig
        assert rollup.read_text() == rollup_orig
        assert threads.read_text() == threads_orig

        wet_synth = apply_rule_synthesis_type_mm30(synth_root, apply=True)
        assert wet_synth.errors == [], wet_synth.errors
        per_hyp_after = per_hyp.read_text()
        assert 'id: "synthesis:h1-foo"' in per_hyp_after, per_hyp_after
        assert 'type: "synthesis"' in per_hyp_after, per_hyp_after
        assert "report:synthesis-h1-foo" not in per_hyp_after
        rollup_after = rollup.read_text()
        assert 'id: "synthesis:rollup"' in rollup_after, rollup_after
        assert 'type: "synthesis"' in rollup_after, rollup_after
        # Emergent-threads file untouched.
        assert threads.read_text() == threads_orig
        ts_synth = synth_tasks.read_text()
        assert "synthesis:h1-foo" in ts_synth
        assert "synthesis:rollup" in ts_synth
        # Unknown synthesis slug preserved (not in path-key set).
        assert "report:synthesis-unknown" in ts_synth
        # File-path mention preserved.
        assert "doc/reports/synthesis/h1-foo.md" in ts_synth
        # No surviving bare ``report:synthesis`` mentions.
        assert "report:synthesis-h1-foo" not in ts_synth
        # ``report:synthesis`` (with no slug suffix) replaced everywhere.
        assert ts_synth.count("report:synthesis ") == 0
        assert ts_synth.count("report:synthesis,") == 0
        assert ts_synth.count("report:synthesis`") == 0

        again_synth = apply_rule_synthesis_type_mm30(synth_root, apply=True)
        assert again_synth.changes == [], f"non-idempotent: {again_synth.changes}"

        # ---- rule: synthesis-type-pl-emergent-threads ----

        pl_root = Path(td) / "pl-fixture"
        pl_root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=pl_root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "t@local"], cwd=pl_root, check=True
        )
        subprocess.run(["git", "config", "user.name", "t"], cwd=pl_root, check=True)
        (pl_root / "doc" / "reports" / "synthesis").mkdir(parents=True)

        pl_threads = pl_root / "doc" / "reports" / "synthesis" / "_emergent-threads.md"
        pl_threads_orig = (
            "---\n"
            'type: "emergent-threads"\n'
            'generated_at: "2026-04-25T11:45:34Z"\n'
            'source_commit: "abc"\n'
            "orphan_question_count: 23\n"
            "---\n"
            "\nbody\n"
        )
        pl_threads.write_text(pl_threads_orig, encoding="utf-8")

        dry_pl = apply_rule_synthesis_type_pl_emergent_threads(pl_root, apply=False)
        assert dry_pl.errors == [], dry_pl.errors
        assert len(dry_pl.changes) > 0
        assert pl_threads.read_text() == pl_threads_orig

        wet_pl = apply_rule_synthesis_type_pl_emergent_threads(pl_root, apply=True)
        assert wet_pl.errors == [], wet_pl.errors
        pl_after = pl_threads.read_text()
        assert 'type: "synthesis"' in pl_after, pl_after
        assert 'id: "synthesis:emergent-threads"' in pl_after, pl_after
        assert 'report_kind: "emergent-threads"' in pl_after, pl_after
        # Existing fields preserved.
        assert 'generated_at: "2026-04-25T11:45:34Z"' in pl_after
        assert "orphan_question_count: 23" in pl_after
        # Order: ``type:`` → ``id:`` → ``report_kind:`` (id and report_kind are
        # inserted immediately after the new ``type:`` line).
        type_idx = pl_after.index("type: ")
        id_idx = pl_after.index('id: "synthesis:emergent-threads"')
        rk_idx = pl_after.index('report_kind: "emergent-threads"')
        assert type_idx < id_idx < rk_idx, (type_idx, id_idx, rk_idx)

        again_pl = apply_rule_synthesis_type_pl_emergent_threads(pl_root, apply=True)
        assert again_pl.changes == [], f"non-idempotent: {again_pl.changes}"

        # Already-canonical case: should be a no-op.
        pl_already = pl_root / "pl-fixture-canonical"
        pl_already.mkdir()
        (pl_already / "doc" / "reports" / "synthesis").mkdir(parents=True)
        pl_already_file = (
            pl_already / "doc" / "reports" / "synthesis" / "_emergent-threads.md"
        )
        pl_already_text = (
            "---\n"
            'id: "synthesis:emergent-threads"\n'
            'type: "synthesis"\n'
            'report_kind: "emergent-threads"\n'
            "---\nbody\n"
        )
        pl_already_file.write_text(pl_already_text, encoding="utf-8")
        noop_pl = apply_rule_synthesis_type_pl_emergent_threads(pl_already, apply=True)
        assert noop_pl.changes == [], noop_pl.changes
        assert pl_already_file.read_text() == pl_already_text

        # ---- rule: synthesis-report-kind-pl-hyp ----

        pl_hyp_root = Path(td) / "pl-hyp-fixture"
        pl_hyp_root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=pl_hyp_root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "t@local"], cwd=pl_hyp_root, check=True
        )
        subprocess.run(["git", "config", "user.name", "t"], cwd=pl_hyp_root, check=True)
        (pl_hyp_root / "doc" / "reports" / "synthesis").mkdir(parents=True)

        # (h1) missing report_kind — should be inserted
        h1 = pl_hyp_root / "doc" / "reports" / "synthesis" / "h01-foo.md"
        h1_orig = (
            "---\n"
            'id: "synthesis:h01-foo"\n'
            'type: "synthesis"\n'
            'hypothesis: "hypothesis:h01-foo"\n'
            "---\n"
            "\nbody\n"
        )
        h1.write_text(h1_orig, encoding="utf-8")
        # (h2) report_kind already present — no-op
        h2 = pl_hyp_root / "doc" / "reports" / "synthesis" / "h02-bar.md"
        h2_orig = (
            "---\n"
            'id: "synthesis:h02-bar"\n'
            'type: "synthesis"\n'
            'report_kind: "hypothesis-synthesis"\n'
            "---\n"
            "\nbody\n"
        )
        h2.write_text(h2_orig, encoding="utf-8")
        # (h3) type is not synthesis — skipped (out of scope; awaits rule
        # ``synthesis-type-mm30``)
        h3 = pl_hyp_root / "doc" / "reports" / "synthesis" / "h03-baz.md"
        h3_orig = '---\nid: "report:synthesis-h03-baz"\ntype: "report"\n---\n\nbody\n'
        h3.write_text(h3_orig, encoding="utf-8")

        dry_hyp = apply_rule_synthesis_report_kind_pl_hyp(pl_hyp_root, apply=False)
        assert dry_hyp.errors == [], dry_hyp.errors
        # Only h01-foo.md should be flagged; multiple line-diff entries are
        # expected because inserting a new line shifts subsequent FM lines.
        kinds_hyp = {c.path.name for c in dry_hyp.changes}
        assert kinds_hyp == {"h01-foo.md"}, kinds_hyp
        assert len(dry_hyp.files_touched) == 1, dry_hyp.files_touched
        assert h1.read_text() == h1_orig

        wet_hyp = apply_rule_synthesis_report_kind_pl_hyp(pl_hyp_root, apply=True)
        assert wet_hyp.errors == [], wet_hyp.errors
        h1_after = h1.read_text()
        assert 'report_kind: "hypothesis-synthesis"' in h1_after, h1_after
        # Order: type: line → report_kind line
        type_idx = h1_after.index('type: "synthesis"')
        rk_idx = h1_after.index('report_kind: "hypothesis-synthesis"')
        assert type_idx < rk_idx
        # Other files untouched
        assert h2.read_text() == h2_orig
        assert h3.read_text() == h3_orig

        again_hyp = apply_rule_synthesis_report_kind_pl_hyp(pl_hyp_root, apply=True)
        assert again_hyp.changes == [], f"non-idempotent: {again_hyp.changes}"

        # ---- rule: pre-registration-type ----

        pre_root = Path(td) / "pre-fixture"
        pre_root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=pre_root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "t@local"], cwd=pre_root, check=True
        )
        subprocess.run(["git", "config", "user.name", "t"], cwd=pre_root, check=True)
        (pre_root / "doc" / "meta").mkdir(parents=True)
        (pre_root / "doc" / "pre-registrations").mkdir(parents=True)

        # (p1) doc/pre-registrations canonical-id, type:plan — should rewrite
        p1 = pre_root / "doc" / "pre-registrations" / "2026-04-12-foo.md"
        p1_orig = (
            "---\n"
            'id: "pre-registration:2026-04-12-foo"\n'
            'type: "plan"\n'
            "committed: 2026-04-12\n"
            "---\nbody\n"
        )
        p1.write_text(p1_orig, encoding="utf-8")
        # (p2) doc/meta with canonical id — should rewrite
        p2 = pre_root / "doc" / "meta" / "pre-registration-bar.md"
        p2_orig = '---\nid: "pre-registration:bar"\ntype: "plan"\n---\nbody\n'
        p2.write_text(p2_orig, encoding="utf-8")
        # (p3) doc/meta with non-canonical id (NS shape) — must NOT rewrite
        p3 = pre_root / "doc" / "meta" / "pre-registration-baz.md"
        p3_orig = '---\nid: "plan:pre-registration-baz"\ntype: "plan"\n---\nbody\n'
        p3.write_text(p3_orig, encoding="utf-8")
        # (p4) already migrated — no-op
        p4 = pre_root / "doc" / "pre-registrations" / "2026-04-13-quux.md"
        p4_orig = (
            "---\n"
            'id: "pre-registration:2026-04-13-quux"\n'
            'type: "pre-registration"\n'
            "---\nbody\n"
        )
        p4.write_text(p4_orig, encoding="utf-8")

        dry_pre = apply_rule_pre_registration_type(pre_root, apply=False)
        assert dry_pre.errors == [], dry_pre.errors
        names_pre = sorted(c.path.name for c in dry_pre.changes)
        assert names_pre == ["2026-04-12-foo.md", "pre-registration-bar.md"], names_pre
        # Dry-run wrote nothing
        assert p1.read_text() == p1_orig
        assert p2.read_text() == p2_orig
        assert p3.read_text() == p3_orig
        assert p4.read_text() == p4_orig

        wet_pre = apply_rule_pre_registration_type(pre_root, apply=True)
        assert wet_pre.errors == [], wet_pre.errors
        assert 'type: "pre-registration"' in p1.read_text()
        assert 'type: "pre-registration"' in p2.read_text()
        # NS-shape file (id starts with plan:) untouched
        assert p3.read_text() == p3_orig
        # Already-canonical file untouched
        assert p4.read_text() == p4_orig

        again_pre = apply_rule_pre_registration_type(pre_root, apply=True)
        assert again_pre.changes == [], f"non-idempotent: {again_pre.changes}"

        # ---- rule: natural-systems-pre-reg-frontmatter (report-only) ----

        ns_root = Path(td) / "ns-fixture"
        ns_root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=ns_root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "t@local"], cwd=ns_root, check=True
        )
        subprocess.run(["git", "config", "user.name", "t"], cwd=ns_root, check=True)
        (ns_root / "doc" / "meta").mkdir(parents=True)

        # (n1) NS-style sparse FM (title + related + created, no id, no type) — should report
        n1 = ns_root / "doc" / "meta" / "pre-registration-q54-temporal-profile.md"
        n1_orig = (
            "---\n"
            "title: 'Pre-registration: Temporal Profile'\n"
            "created: '2026-03-30'\n"
            "---\n"
            "\nbody\n"
        )
        n1.write_text(n1_orig, encoding="utf-8")
        # (n2) FM with type: but no id: — should report
        n2 = ns_root / "doc" / "meta" / "pre-registration-t085-t086.md"
        n2_orig = '---\ntype: "plan"\n---\nbody\n'
        n2.write_text(n2_orig, encoding="utf-8")
        # (n3) FM with both id: and type: — should NOT be reported
        n3 = ns_root / "doc" / "meta" / "pre-registration-t214.md"
        n3_orig = '---\nid: "plan:pre-registration-t214"\ntype: "plan"\n---\nbody\n'
        n3.write_text(n3_orig, encoding="utf-8")

        dry_ns = apply_rule_natural_systems_pre_reg_frontmatter(ns_root, apply=False)
        assert dry_ns.errors == [], dry_ns.errors
        names_ns = sorted(c.path.name for c in dry_ns.changes)
        assert names_ns == [
            "pre-registration-q54-temporal-profile.md",
            "pre-registration-t085-t086.md",
        ], names_ns
        # All entries are manual-suggested.
        assert all(c.kind == "manual-suggested" for c in dry_ns.changes)
        # Suggestion includes <TODO> placeholders for committed: and spec:.
        for c in dry_ns.changes:
            assert "<TODO>" in c.after, c.after
            assert "committed:" in c.after, c.after
            assert "spec:" in c.after, c.after
            assert 'type: "pre-registration"' in c.after, c.after

        # apply=True must STILL not mutate (report-only rule).
        wet_ns = apply_rule_natural_systems_pre_reg_frontmatter(ns_root, apply=True)
        assert n1.read_text() == n1_orig, "report-only rule must not write"
        assert n2.read_text() == n2_orig, "report-only rule must not write"
        assert n3.read_text() == n3_orig, "report-only rule must not write"
        # Re-running yields the same suggestions (the rule is stable; its
        # ``changes`` count does not drop to zero between invocations because
        # it never rewrites files — operator must apply manually). This is
        # the "idempotent on re-apply" contract for a report-only rule:
        # output is deterministic.
        assert len(wet_ns.changes) == len(dry_ns.changes)

        # ---- rule 2: specs-frontmatter-backfill ----

        (root / "specs").mkdir()
        # (s1) dated, no frontmatter, has H1 — should be backfilled
        spec_drift = root / "specs" / "2026-03-16-foo-design.md"
        spec_drift_orig = (
            "# Foo Design: A Worked Example\n\n**Date:** 2026-03-16\n\nBody.\n"
        )
        spec_drift.write_text(spec_drift_orig, encoding="utf-8")
        # (s2) non-dated, no frontmatter, no H1 — title falls back to basename
        spec_no_h1 = root / "specs" / "research-notes.md"
        spec_no_h1.write_text("Just some prose.\n", encoding="utf-8")
        # (s3) already has frontmatter — must be left alone
        spec_canon = root / "specs" / "2026-04-22-bar-design.md"
        spec_canon_text = (
            '---\nid: "spec:2026-04-22-bar-design"\ntype: "spec"\n'
            'title: "Bar"\ndate: 2026-04-22\nstatus: design\n---\n\nBody.\n'
        )
        spec_canon.write_text(spec_canon_text, encoding="utf-8")
        # (s4) title with characters that need YAML escaping
        spec_special = root / "specs" / "2026-04-01-quoted-title.md"
        spec_special.write_text(
            '# Spec: "Quoted" — em-dash & path\\ok\n\nBody.\n',
            encoding="utf-8",
        )

        # Dry-run rule 2
        dry2 = apply_rule_specs_frontmatter_backfill(root, apply=False)
        assert dry2.errors == [], f"errors: {dry2.errors}"
        names = sorted(c.path.name for c in dry2.changes)
        assert names == [
            "2026-03-16-foo-design.md",
            "2026-04-01-quoted-title.md",
            "research-notes.md",
        ], names
        assert not any(c.path == spec_canon for c in dry2.changes)
        # Dry-run did not write
        assert spec_drift.read_text() == spec_drift_orig
        assert spec_canon.read_text() == spec_canon_text

        # Apply rule 2
        wet2 = apply_rule_specs_frontmatter_backfill(root, apply=True)
        assert wet2.errors == [], f"errors: {wet2.errors}"
        # Drifted dated spec: id derived from basename, date from prefix, title from H1
        d_text = spec_drift.read_text()
        assert d_text.startswith("---\n")
        assert 'id: "spec:2026-03-16-foo-design"' in d_text
        assert 'type: "spec"' in d_text
        assert 'title: "Foo Design: A Worked Example"' in d_text
        assert "date: 2026-03-16" in d_text
        assert 'status: "design"' in d_text
        # Original body intact
        assert "Body." in d_text
        # No-H1 non-dated spec: title falls back to basename, no date field
        n_text = spec_no_h1.read_text()
        assert 'id: "spec:research-notes"' in n_text
        assert 'title: "research-notes"' in n_text
        assert "date:" not in n_text.split("---", 2)[1]
        # Already-canonical spec: byte-identical
        assert spec_canon.read_text() == spec_canon_text
        # Special-character title: YAML-escaped properly
        s_text = spec_special.read_text()
        assert 'title: "Spec: \\"Quoted\\" — em-dash & path\\\\ok"' in s_text, s_text

        # Idempotence
        again2 = apply_rule_specs_frontmatter_backfill(root, apply=True)
        assert again2.changes == [], f"non-idempotent: {again2.changes}"

        click.echo("self-test: PASS")


# ---------- CLI ----------


RULES = {
    "report-id-prefix": apply_rule_report_id_prefix,
    "synthesis-type-mm30": apply_rule_synthesis_type_mm30,
    "synthesis-type-pl-emergent-threads": apply_rule_synthesis_type_pl_emergent_threads,
    "synthesis-report-kind-pl-hyp": apply_rule_synthesis_report_kind_pl_hyp,
    "pre-registration-type": apply_rule_pre_registration_type,
    "natural-systems-pre-reg-frontmatter": apply_rule_natural_systems_pre_reg_frontmatter,
    "specs-frontmatter-backfill": apply_rule_specs_frontmatter_backfill,
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
        raise click.UsageError(
            "--rule is required (choose one: " + ", ".join(sorted(RULES)) + ")"
        )
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
