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

# (relative_path, distinctive_substring) for every legitimate mention
# present in the tree today. Matched by stable substring, not line number,
# since line numbers drift. Add new entries here only for genuine
# store/location descriptions or command-internal specs -- never for an
# instruction that tells an agent to read a task file's contents.
_ALLOWLIST: set[tuple[str, str]] = {
    (
        "commands/big-picture.md",
        "glob `tasks/*.md` and `tasks/done/*.md`; parse frontmatter",
    ),
    ("commands/create-graph.md", "Task files in `tasks/active.md` and `tasks/done/*.md`"),
    (
        "commands/create-graph.md",
        "Keep task links in `tasks/*.md` `related:` / `blocked-by:` fields",
    ),
    (
        "commands/next-steps.md",
        "Accepted work belongs in `science tasks ...` and `tasks/active.md`.",
    ),
    (
        "commands/next-steps.md",
        "to move the N done/retired entries from `tasks/active.md` to `tasks/done/YYYY-MM.md`.",
    ),
    (
        "commands/next-steps.md",
        "so you don't need to open the archive files yourself.",
    ),
    (
        "commands/discuss.md",
        "update its description in `tasks/active.md` to reflect the new framing.",
    ),
    (
        "commands/status.md",
        "N done/retired task(s) still in `tasks/active.md`. Run `science tasks archive --apply`",
    ),
    ("commands/status.md", "to move them to `tasks/done/YYYY-MM.md`."),
    ("commands/tasks.md", "Manage the project task queue in `tasks/active.md`."),
    (
        "commands/tasks.md",
        "the authoritative store: it lives in the repo (`tasks/active.md`),",
    ),
    (
        "commands/tasks.md",
        "no longer belongs in `tasks/active.md` or `tasks/done/YYYY-MM.md`",
    ),
    (
        "commands/tasks.md",
        "Interactive sweep to retype legacy untyped blockers in `tasks/active.md`.",
    ),
    ("commands/create-project.md", "### `tasks/active.md`"),
    ("templates/agents-md.md", "Tasks live in `tasks/active.md`, managed by `science tasks`"),
    ("templates/agents-md.md", "to `tasks/done/YYYY-MM.md`."),
    ("templates/agents-md.md", "- Active tasks: `tasks/active.md`"),
    ("templates/core-overview.md", "- Active tasks: `tasks/active.md`"),
}


def _is_allowlisted(relpath: str, line: str) -> bool:
    return any(relpath == path and substring in line for path, substring in _ALLOWLIST)


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
