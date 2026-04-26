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
                FileChange(path=path, kind=kind, before=a.strip(), after=b.strip(), line_no=i)
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
        assert len(mention_changes) == 3, f"expected 3 mention rewrites, got {mention_changes}"
        # Files unchanged after dry-run
        assert 'doc:2026-04-25-foo' in drifted.read_text(), "dry-run must not write"
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
        assert "doc:reports/2026-04-25-foo" not in ts, "infix-form mention must be rewritten"
        assert "doc:reports/synthesis" in ts, "directory ref must survive"
        assert "doc:reports/synthesis/_emergent-threads" in ts, "synthesis subref must survive"
        assert "doc/reports/2026-04-25-foo.md" in ts, "file-path mention must survive"
        assert "doc:2026-04-13-baz" in ts, "bare interpretation mention must survive"
        # Bare report mention: every `doc:2026-04-25-foo` (no `reports/` infix)
        # should now read `report:2026-04-25-foo`.
        assert ts.count("doc:2026-04-25-foo") == 0, "bare report mentions must be rewritten"
        assert ts.count("report:2026-04-25-foo") >= 3, "expected 3 occurrences after rewrite"
        assert canon.read_text() == canon_text, "canonical report must be untouched"
        assert synth.read_text() == synth_text, "synthesis file must be untouched"
        assert interp.read_text() == interp_text, "interpretation must be untouched"

        # Idempotence
        again = apply_rule_report_id_prefix(root, apply=True)
        assert again.changes == [], f"non-idempotent: {again.changes}"

        # ---- rule 2: specs-frontmatter-backfill ----

        (root / "specs").mkdir()
        # (s1) dated, no frontmatter, has H1 — should be backfilled
        spec_drift = root / "specs" / "2026-03-16-foo-design.md"
        spec_drift_orig = (
            "# Foo Design: A Worked Example\n"
            "\n"
            "**Date:** 2026-03-16\n"
            "\n"
            "Body.\n"
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
