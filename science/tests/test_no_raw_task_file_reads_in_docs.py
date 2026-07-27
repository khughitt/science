"""Slice 2 Task 4 content guard: no agent-facing doc instructs an agent to read
the raw CONTENTS of a CLI-owned task file.

``tasks/active/*.md`` and ``tasks/done/*.md`` are the CLI's own task store.
Task 3 replaced every agent-facing "Read `tasks/active.md`" / "scan
`tasks/done/`" style instruction with a bounded ``science tasks ...``
equivalent, because reading those files directly floods agent context. This
is the backstop: it fails closed on ANY line in the agent-facing surface that
references ``tasks/active/``, the retired aggregate ``tasks/active.md``,
``tasks/done``, or ``tasks/*.md`` unless that line is on the allow-list below
(a store/location description, a command-internal ingest spec, an authoring
convention, or a scaffold header — never a "read this file's contents"
directive).

See docs/plans/2026-07-26-context-budget-slice2-implementation.md.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Current agent- and user-facing surface only. Historical design/plan prose and
# skills/generated/ (the generated distribution) are intentionally excluded.
_CURRENT_DOC_DIRS = (
    "commands",
    "skills",
    "templates",
    "agents",
    "references",
    "docs/user-guide",
    "docs/conventions",
)

# Broad catch: any mention of the CLI-owned task-file paths at all. Fails
# closed — a brand new mention (legitimate or not) trips this and forces a
# classification decision rather than silently passing.
_MENTION = re.compile(
    r"tasks/(?:active(?:\.md|/)|done|\*\.md|\*)|\bactive\.md priorities\b",
    flags=re.IGNORECASE,
)
_LEGACY_ACTIVE_STORE = re.compile(
    r"tasks/active\.md|\bactive\.md priorities\b",
    flags=re.IGNORECASE,
)
_RETIRED_ARCHIVE_SURFACE = re.compile(
    r"\bscience tasks archive\b|`tasks archive(?:\s[^`]*)?`|count_archivable|archive_lag"
)

# (relative_path, full_trimmed_line) for every legitimate mention present in
# the tree today. Matched by EXACT equality against `line.strip()`, not
# substring containment and not line number (line numbers drift). Each entry
# must be the complete trimmed text of the real line, not a distinctive
# fragment: substring containment previously let an allow-listed line be
# silently extended with a raw-read directive (e.g. appending "Read it before
# making changes.") and still match, which is the exact hole this guard
# exists to close. Add new entries here only for genuine store/location
# descriptions or command-internal specs -- never for an instruction that
# tells an agent to read a task file's contents. Brittleness is intentional:
# any future wording change to one of these lines trips the guard and forces
# re-classification (fail-closed).
_ALLOWLIST: set[tuple[str, str]] = {
    (
        "commands/big-picture.md",
        "- `tasks`: for this hypothesis and each resolved question, run `uv run "
        "science tasks list --all <research-aspect-flags> --related=<ref> "
        "--format json` to collect open work. For terminal work, derive "
        "`<task-window-start>` from `--since` when present or the project's "
        "`created` date otherwise, then run `uv run science tasks list --status "
        "done --since <task-window-start> <research-aspect-flags> --related=<ref> "
        "--format json` and `uv run science tasks list --status retired --since "
        "<task-window-start> <research-aspect-flags> --related=<ref> --format "
        "json`. Merge and deduplicate the already aspect-filtered rows by task ID. The "
        "CLI reads one YAML-frontmatter file per open task under `tasks/active/`; "
        "do not open task-store files directly.",
    ),
    (
        "commands/create-graph.md",
        "- Task records: one YAML-frontmatter file per open task under `tasks/active/`,",
    ),
    ("commands/create-graph.md", "plus monthly done ledgers under `tasks/done/*.md`"),
    ("commands/create-project.md", "### `tasks/active/`"),
    (
        "commands/create-project.md",
        "add` writes one YAML-frontmatter file per open task under `tasks/active/`;",
    ),
    (
        "commands/create-project.md",
        "to monthly `tasks/done/YYYY-MM.md` ledgers. Use `science tasks list` and",
    ),
    (
        "commands/next-steps.md",
        "`tasks/done/YYYY-MM.md` ledger whose month intersects that window, including",
    ),
    ("commands/tasks.md", "under `tasks/active/`."),
    (
        "commands/tasks.md",
        "> the authoritative store: it lives in the repo (`tasks/active/` for open work,",
    ),
    ("commands/tasks.md", "> `tasks/done/YYYY-MM.md` for terminal records),"),
    (
        "commands/tasks.md",
        "`tasks/archive.md` is for historical task aliases only. Use the same "
        "`## [tNNN] Title` heading shape when old documents still cite a task "
        "ID that no longer belongs in `tasks/active/` or "
        "`tasks/done/YYYY-MM.md`; include brief metadata such as `status: "
        "archived` and `replacement: task:tNNN` when there is a successor. Do "
        "not use it for current operational task history.",
    ),
    (
        "templates/agents-md.md",
        "`tasks/active/`, managed by `science tasks` (or the `/science:tasks` slash",
    ),
    (
        "templates/agents-md.md",
        "`tasks/done/YYYY-MM.md`; no separate archive step is needed.",
    ),
    (
        "templates/agents-md.md",
        "- Active tasks: `science tasks list` (`tasks/active/`, one file per open task)",
    ),
    (
        "templates/core-overview.md",
        "- Active tasks: `science tasks list` (`tasks/active/`, one file per open task)",
    ),
    (
        "references/project-structure.md",
        "- `tasks/active/` — one YAML-frontmatter file per open task",
    ),
    (
        "references/project-structure.md",
        "- `tasks/done/YYYY-MM.md` — monthly ledgers for completed and retired tasks",
    ),
    (
        "docs/user-guide/big-picture.md",
        "Open work follows the same small-record principle: `tasks/active/` stores one",
    ),
    (
        "docs/user-guide/big-picture.md",
        "directly to a monthly `tasks/done/YYYY-MM.md` ledger. Keeping each open record",
    ),
    (
        "docs/user-guide/project-layout.md",
        "| `tasks/` | Operational work: one YAML-frontmatter file per open task under `tasks/active/`, with terminal records in monthly `tasks/done/YYYY-MM.md` ledgers. |",
    ),
}


def _is_allowlisted(relpath: str, line: str) -> bool:
    return (relpath, line.strip()) in _ALLOWLIST


def _is_offender(relpath: str, line: str) -> bool:
    """A line is an offender iff it mentions a CLI-owned task file and is not allow-listed."""
    return bool(_MENTION.search(line)) and not _is_allowlisted(relpath, line)


def _raw_read_offenders(root: Path = ROOT) -> list[str]:
    offenders: list[str] = []
    for dirname in _CURRENT_DOC_DIRS:
        base = root / dirname
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            if md.is_relative_to(root / "skills" / "generated"):
                continue
            relpath = md.relative_to(root).as_posix()
            for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), start=1):
                if _is_offender(relpath, line):
                    offenders.append(f"  {relpath}:{lineno}: {line.strip()}")
    return offenders


def test_no_raw_task_file_read_instructions_in_docs() -> None:
    offenders = _raw_read_offenders()
    assert not offenders, (
        "Found agent-facing doc line(s) that look like a raw-task-file read "
        "directive for a CLI-owned task file (`tasks/active.md` / "
        "`tasks/done/...`). Replace it with a bounded `science tasks list ...` "
        "equivalent (see docs/plans/2026-07-26-context-budget-slice2-implementation.md), "
        "or if it is a legitimate store/location description or command-internal "
        "spec, add it to _ALLOWLIST with a reason:\n" + "\n".join(offenders)
    )


def test_raw_read_scan_includes_user_guide_and_conventions(tmp_path: Path) -> None:
    samples = {
        "docs/user-guide/future.md": "Read every `tasks/active/*.md` file.",
        "docs/conventions/future.md": "Scan `tasks/done/` before starting.",
    }
    for relpath, text in samples.items():
        path = tmp_path / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    offenders = "\n".join(_raw_read_offenders(tmp_path))
    assert "docs/user-guide/future.md" in offenders
    assert "docs/conventions/future.md" in offenders


def test_bare_aggregate_priority_wording_is_flagged() -> None:
    sample = "These should match the active.md priorities."
    assert _is_offender("templates/example.md", sample)


def _current_markdown_lines() -> list[tuple[str, int, str]]:
    lines: list[tuple[str, int, str]] = []
    for dirname in _CURRENT_DOC_DIRS:
        base = ROOT / dirname
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            if md.is_relative_to(ROOT / "skills" / "generated"):
                continue
            relpath = md.relative_to(ROOT).as_posix()
            lines.extend(
                (relpath, lineno, line)
                for lineno, line in enumerate(
                    md.read_text(encoding="utf-8").splitlines(),
                    start=1,
                )
            )
    return lines


def test_current_docs_do_not_describe_the_legacy_aggregate_active_store() -> None:
    offenders = [
        f"  {relpath}:{lineno}: {line.strip()}"
        for relpath, lineno, line in _current_markdown_lines()
        if _LEGACY_ACTIVE_STORE.search(line)
    ]
    assert not offenders, (
        "Current user, command, template, and reference docs must describe "
        "`tasks/active/` one-file-per-task storage, not the retired aggregate "
        "`tasks/active.md` layout. Historical plans and audits are intentionally "
        "outside this guard:\n" + "\n".join(offenders)
    )


def test_current_docs_do_not_recommend_retired_task_archive_surfaces() -> None:
    offenders = [
        f"  {relpath}:{lineno}: {line.strip()}"
        for relpath, lineno, line in _current_markdown_lines()
        if _RETIRED_ARCHIVE_SURFACE.search(line)
    ]
    assert not offenders, (
        "Current docs must not recommend the retired `science tasks archive` "
        "command or its removed archive-lag health surface. Historical plans "
        "and audits are intentionally outside this guard:\n" + "\n".join(offenders)
    )


def test_primary_task_store_docs_explain_the_split_layout() -> None:
    docs = (
        "docs/user-guide/big-picture.md",
        "commands/big-picture.md",
        "commands/create-graph.md",
        "commands/create-project.md",
        "commands/tasks.md",
        "templates/agents-md.md",
        "templates/core-overview.md",
        "references/project-structure.md",
    )
    for relpath in docs:
        text = (ROOT / relpath).read_text(encoding="utf-8")
        assert "tasks/active/" in text, (
            f"{relpath} must name the current `tasks/active/` store"
        )
        assert re.search(
            r"one\s+(?:YAML-frontmatter\s+)?file\s+per\s+(?:open|active)\s+task",
            text,
            flags=re.IGNORECASE,
        ), f"{relpath} must explain that `tasks/active/` stores one file per open task"


def test_all_allowlisted_lines_are_admitted_verbatim() -> None:
    # Exact-match must still admit every real line in the tree today -- the
    # fix must not become over-strict and start flagging the legitimate
    # mentions it was built to allow.
    for relpath, line in sorted(_ALLOWLIST):
        real_lines = {
            candidate.strip()
            for candidate in (ROOT / relpath).read_text(encoding="utf-8").splitlines()
        }
        assert line in real_lines, f"stale allow-list entry: {relpath}: {line!r}"
        assert not _is_offender(relpath, line), (
            f"allow-listed line should be admitted verbatim: {relpath}: {line!r}"
        )


# Verbatim shapes removed by Task 3 (see the corrected Task 4 brief). Every
# one of these must trip the detector -- this is the "before" side of the
# guard that a static allow-list alone cannot demonstrate, since Task 3 is
# already committed and the real tree is now clean.
_FORBIDDEN_SAMPLES = (
    "Read `tasks/active.md` if it exists.",
    "Read every `tasks/active/*.md` file before deciding what to do.",
    "Read `tasks/active.md` for full task descriptions. Note the total count and distribution.",
    "- Check `tasks/done/` for recently completed tasks that might inform gap analysis",
    "2. Recent completed tasks: scan `tasks/done/` for the most recent file",
    "- Recently completed tasks from `tasks/done/`",
    "From `tasks/active.md`, show:",
    "   - `tasks/active.md`",
    "4. `tasks/active.md`",
    "3. `tasks/active.md`",
    "These should match the active.md priorities.",
)


def test_forbidden_task_file_read_directives_are_flagged() -> None:
    # A path that appears nowhere in _ALLOWLIST: proves these samples are
    # flagged on their own merits, not by accidental substring collision
    # with a real file's allow-listed entry.
    unknown_relpath = "commands/__not_a_real_doc__.md"
    for sample in _FORBIDDEN_SAMPLES:
        assert _MENTION.search(sample), f"sample should trip the tasks/ mention regex: {sample!r}"
        assert not _is_allowlisted(unknown_relpath, sample), (
            f"sample should not be allow-listable: {sample!r}"
        )
        assert _is_offender(unknown_relpath, sample), f"detector should flag forbidden sample: {sample!r}"


# Regression for the exact-match fix: appending a raw-read clause to an
# allow-listed line used to slip through undetected because the old check
# was `entry in line` (substring containment) -- the allow-listed text was
# still *contained* in the mutated line. Exact trimmed-line equality closes
# this. Each case pairs a real allow-listed (path, line) with an appended
# clause that plausibly reads as "go open this file."
_APPENDED_MUTATIONS: tuple[tuple[str, str, str], ...] = (
    (
        "commands/create-graph.md",
        "- Task records: one YAML-frontmatter file per open task under `tasks/active/`,",
        " Read it before making changes.",
    ),
    (
        "templates/agents-md.md",
        "- Active tasks: `science tasks list` (`tasks/active/`, one file per open task)",
        " — read it top to bottom every session.",
    ),
    (
        "commands/create-project.md",
        "### `tasks/active/`",
        " Read it before making changes.",
    ),
    (
        "references/project-structure.md",
        "- `tasks/active/` — one YAML-frontmatter file per open task",
        " — read it top to bottom every session.",
    ),
)


def test_appending_a_raw_read_clause_to_an_allowlisted_line_is_flagged() -> None:
    for relpath, legit_line, suffix in _APPENDED_MUTATIONS:
        assert (relpath, legit_line) in _ALLOWLIST, (
            f"fixture drift: {(relpath, legit_line)!r} is no longer a real allow-list entry"
        )
        mutated = legit_line + suffix
        assert _is_offender(relpath, mutated), (
            f"appending a raw-read clause to an allow-listed line must be flagged "
            f"(exact-match hole regression): {relpath}: {mutated!r}"
        )
