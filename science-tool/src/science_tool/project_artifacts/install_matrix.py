"""Install-matrix decision table.

Pure logic: maps (Status, header presence, hash known, flags) to an Action.
Per spec 'Data flow' install matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from science_tool.project_artifacts.status import Status


class Action(str, Enum):
    INSTALL = "install"
    NO_OP = "no_op"
    REFUSE_SUGGEST_UPDATE = "refuse_suggest_update"
    REFUSE_LOCALLY_MODIFIED = "refuse_locally_modified"
    REFUSE_NEEDS_ADOPT = "refuse_needs_adopt"
    ADOPT_IN_PLACE = "adopt_in_place"
    REFUSE_NEEDS_FORCE_ADOPT = "refuse_needs_force_adopt"
    FORCE_ADOPT = "force_adopt"
    REFUSE_WRONG_NAME = "refuse_wrong_name"


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str


def decide(
    *,
    status: Status,
    header_present: bool,
    hash_known_to_registry: bool,
    wrong_name_in_header: bool,
    adopt: bool,
    force_adopt: bool,
) -> Decision:
    """Decide what to do given the install_target's classified state and flags."""
    if status is Status.MISSING:
        return Decision(Action.INSTALL, "install_target missing; install canonical")

    if header_present and wrong_name_in_header:
        return Decision(
            Action.REFUSE_WRONG_NAME,
            "installed file has a managed header for a different artifact name",
        )

    if status is Status.CURRENT:
        return Decision(Action.NO_OP, "already current; no action needed")

    if status is Status.STALE:
        return Decision(
            Action.REFUSE_SUGGEST_UPDATE,
            "installed bytes match a previous version; run `update` instead of `install`",
        )

    if status is Status.LOCALLY_MODIFIED:
        return Decision(
            Action.REFUSE_LOCALLY_MODIFIED,
            "installed file has a managed header but the body matches no known version; "
            "use `diff` then `update --force` to overwrite",
        )

    if status is Status.UNTRACKED:
        if hash_known_to_registry:
            if adopt:
                return Decision(
                    Action.ADOPT_IN_PLACE,
                    "untracked file matches a known version; rewriting header in place",
                )
            return Decision(
                Action.REFUSE_NEEDS_ADOPT,
                "untracked file matches a known historical version; "
                "re-run with --adopt to claim it (writes the managed header in place)",
            )
        if force_adopt:
            return Decision(
                Action.FORCE_ADOPT,
                "untracked file does not match any known version; "
                "force-adopting (byte-replace with canonical; writes .pre-install.bak)",
            )
        return Decision(
            Action.REFUSE_NEEDS_FORCE_ADOPT,
            "untracked file does not match any known version; re-run with --force-adopt to overwrite",
        )

    # PINNED / PINNED_BUT_LOCALLY_MODIFIED — install is not the right verb
    return Decision(
        Action.REFUSE_LOCALLY_MODIFIED,
        f"install not applicable for status {status.value!r}; use `unpin` or `update`",
    )
