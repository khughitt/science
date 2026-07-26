"""Verify the human-legibility marks on a run's commits (design §3).

NOT a security boundary: a process that writes commits can set any author and any
trailer. The authoritative binding is the supervisor-recorded base..head range. A
mismatch is still worth quarantining on, because it means commits the run did not
account for landed inside its own range.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from science_tool.autonomy.extract import _git

TRAILER_KEY = "Science-Run"
#: Design §3: unattended commits set the author to `<role> <agent@science.local>`. The
#: role varies per run; the mailbox does not.
AGENT_EMAIL = "agent@science.local"
_SEP = "\x1e"  # record separator -- cannot occur in an author name or a trailer value


class MarkIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    commit: str
    reason: str


def verify_marks(
    repo_root: Path, base: str, head: str, *, run_id: str, agent: str
) -> tuple[MarkIssue, ...]:
    raw = _git(
        repo_root,
        "log",
        f"--format=%H{_SEP}%an{_SEP}%ae{_SEP}%(trailers:key={TRAILER_KEY},valueonly){_SEP}",
        f"{base}..{head}",
    ).decode("utf-8", "replace")

    issues: list[MarkIssue] = []
    for entry in raw.split(f"{_SEP}\n"):
        if not entry.strip():
            continue
        commit, author, email, trailers = entry.split(_SEP, 3)
        values = [line.strip() for line in trailers.splitlines() if line.strip()]
        if not values:
            issues.append(MarkIssue(commit=commit, reason=f"no {TRAILER_KEY} trailer"))
        elif any(value != run_id for value in values):
            issues.append(
                MarkIssue(commit=commit, reason=f"{TRAILER_KEY} names another run: {values}")
            )
        # One issue for the identity, not two: `<role> <mailbox>` is a single spelling,
        # and reporting the halves separately would double-count one wrong author.
        if author != agent or email != AGENT_EMAIL:
            issues.append(
                MarkIssue(
                    commit=commit,
                    reason=(
                        f"author {author} <{email}> is not this run's agent "
                        f"{agent} <{AGENT_EMAIL}>"
                    ),
                )
            )
    return tuple(issues)
