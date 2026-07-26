"""Slice 2 Task 4 content guard: no agent-facing doc instructs an agent to read
the raw CONTENTS of a CLI-owned task file.

``tasks/active.md`` and ``tasks/done/*.md`` are the CLI's own task store.
Task 3 replaced every agent-facing "Read `tasks/active.md`" / "scan
`tasks/done/`" style instruction with a bounded ``science tasks ...``
equivalent, because reading those files directly floods agent context. This
is the backstop: it fails closed on ANY line in the agent-facing surface that
references ``tasks/active.md``, ``tasks/done``, or ``tasks/*.md`` unless that
line is on the allow-list below (a store/location description, a
command-internal ingest spec, an archive notice anchored on a `science
tasks ...` command, an authoring convention, or a scaffold header — never a
"read this file's contents" directive).

See docs/plans/2026-07-26-context-budget-slice2-implementation.md.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Agent-facing surface only. docs/ (design/plan prose) and codex-skills/
# (generated mirror of commands/) are intentionally excluded.
_SCAN_DIRS = ("commands", "skills", "templates", "agents", "references")

# Broad catch: any mention of the CLI-owned task-file paths at all. Fails
# closed — a brand new mention (legitimate or not) trips this and forces a
# classification decision rather than silently passing.
_MENTION = re.compile(r"tasks/(?:active\.md|done|\*\.md|\*)")

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
        "- `tasks`: glob `tasks/*.md` and `tasks/done/*.md`; parse frontmatter; "
        "include entries whose `related:` mentions this hypothesis or any of its "
        "resolved questions **AND** whose resolved aspects intersect "
        "`research_filter`. If `tasks/active.md` is a single aggregated file "
        "(common pattern, e.g., mm30), scan its body for per-task headings and "
        "`related:` metadata instead of expecting one file per task.",
    ),
    ("commands/create-graph.md", "- Task files in `tasks/active.md` and `tasks/done/*.md`"),
    (
        "commands/create-graph.md",
        "2. Keep task links in `tasks/*.md` `related:` / `blocked-by:` fields using canonical IDs.",
    ),
    (
        "commands/next-steps.md",
        "Accepted work belongs in `science tasks ...` and `tasks/active.md`.",
    ),
    (
        "commands/next-steps.md",
        "> Preview with `science tasks archive`, then run `science tasks archive "
        "--apply` to move the N done/retired entries from `tasks/active.md` to "
        "`tasks/done/YYYY-MM.md`.",
    ),
    (
        "commands/next-steps.md",
        "**Also check recent completions, not just the active queue.** Work "
        "shipped in done files lives in `tasks/done/<YYYY-MM>.md`, not "
        "`active.md`; derive the recent-progress window first: use the date of "
        "the prior `next-steps` analysis when one exists, otherwise use the "
        "explicit lookback window for this run. Then run `science tasks list "
        "--status done --since <window-start>` — under the hood this will scan "
        "every `tasks/done/YYYY-MM.md` file whose month intersects that window, "
        "including prior-month files when the window crosses a month boundary, "
        "so you don't need to open the archive files yourself. Do not stop at "
        "the current month file or assume the prior month is irrelevant just "
        "because it is large. For each returned row whose `completed:` date "
        "falls inside the window, treat those rows as recent progress, not "
        "status drift. Without this, recently-shipped work is invisible: a run "
        'can wrongly conclude "no movement" or a "stalled program" when tasks '
        "in fact completed during the window.",
    ),
    (
        "commands/discuss.md",
        "5. **Task reframing check:** Review whether the discussion reframes the "
        "meaning of any existing tasks. If a task's purpose or scope has "
        "changed, update its description in `tasks/active.md` to reflect the "
        "new framing.",
    ),
    (
        "commands/status.md",
        "> N done/retired task(s) still in `tasks/active.md`. Run `science tasks archive --apply`",
    ),
    ("commands/status.md", "> to move them to `tasks/done/YYYY-MM.md`."),
    ("commands/tasks.md", "Manage the project task queue in `tasks/active.md`."),
    (
        "commands/tasks.md",
        "> the authoritative store: it lives in the repo (`tasks/active.md`),",
    ),
    (
        "commands/tasks.md",
        "`tasks/archive.md` is for historical task aliases only. Use the same "
        "`## [tNNN] Title` heading shape when old documents still cite a task "
        "ID that no longer belongs in `tasks/active.md` or "
        "`tasks/done/YYYY-MM.md`; include brief metadata such as `status: "
        "archived` and `replacement: task:tNNN` when there is a successor. Do "
        "not use it for current operational task history.",
    ),
    (
        "commands/tasks.md",
        "Interactive sweep to retype legacy untyped blockers in `tasks/active.md`.",
    ),
    ("commands/create-project.md", "### `tasks/active.md`"),
    (
        "templates/agents-md.md",
        "- Tasks live in `tasks/active.md`, managed by `science tasks` (or",
    ),
    ("templates/agents-md.md", "to `tasks/done/YYYY-MM.md`."),
    ("templates/agents-md.md", "- Active tasks: `tasks/active.md`"),
    ("templates/core-overview.md", "- Active tasks: `tasks/active.md`"),
}


def _is_allowlisted(relpath: str, line: str) -> bool:
    return (relpath, line.strip()) in _ALLOWLIST


def _is_offender(relpath: str, line: str) -> bool:
    """A line is an offender iff it mentions a CLI-owned task file and is not allow-listed."""
    return bool(_MENTION.search(line)) and not _is_allowlisted(relpath, line)


def test_no_raw_task_file_read_instructions_in_docs() -> None:
    offenders: list[str] = []
    for dirname in _SCAN_DIRS:
        base = ROOT / dirname
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            relpath = md.relative_to(ROOT).as_posix()
            for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), start=1):
                if _is_offender(relpath, line):
                    offenders.append(f"  {relpath}:{lineno}: {line.strip()}")
    assert not offenders, (
        "Found agent-facing doc line(s) that look like a raw-task-file read "
        "directive for a CLI-owned task file (`tasks/active.md` / "
        "`tasks/done/...`). Replace it with a bounded `science tasks list ...` "
        "equivalent (see docs/plans/2026-07-26-context-budget-slice2-implementation.md), "
        "or if it is a legitimate store/location description or command-internal "
        "spec, add it to _ALLOWLIST with a reason:\n" + "\n".join(offenders)
    )


def test_all_allowlisted_lines_are_admitted_verbatim() -> None:
    # Exact-match must still admit every real line in the tree today -- the
    # fix must not become over-strict and start flagging the legitimate
    # mentions it was built to allow.
    for relpath, line in sorted(_ALLOWLIST):
        assert not _is_offender(relpath, line), (
            f"allow-listed line should be admitted verbatim: {relpath}: {line!r}"
        )


# Verbatim shapes removed by Task 3 (see the corrected Task 4 brief). Every
# one of these must trip the detector -- this is the "before" side of the
# guard that a static allow-list alone cannot demonstrate, since Task 3 is
# already committed and the real tree is now clean.
_FORBIDDEN_SAMPLES = (
    "Read `tasks/active.md` if it exists.",
    "Read `tasks/active.md` for full task descriptions. Note the total count and distribution.",
    "- Check `tasks/done/` for recently completed tasks that might inform gap analysis",
    "2. Recent completed tasks: scan `tasks/done/` for the most recent file",
    "- Recently completed tasks from `tasks/done/`",
    "From `tasks/active.md`, show:",
    "   - `tasks/active.md`",
    "4. `tasks/active.md`",
    "3. `tasks/active.md`",
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
        "commands/tasks.md",
        "Manage the project task queue in `tasks/active.md`.",
        " Read it before making changes.",
    ),
    (
        "templates/agents-md.md",
        "- Active tasks: `tasks/active.md`",
        " — read it top to bottom every session.",
    ),
    (
        "commands/create-project.md",
        "### `tasks/active.md`",
        " Read it before making changes.",
    ),
    (
        "commands/tasks.md",
        "Interactive sweep to retype legacy untyped blockers in `tasks/active.md`.",
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
