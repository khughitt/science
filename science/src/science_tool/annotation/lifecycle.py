# science/src/science_tool/annotation/lifecycle.py
"""Status mutation with prov:wasRevisionOf preservation.

See docs/plans/2026-05-10-annotation-system-spec.md §Status lifecycle.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Optional

from science_tool.annotation.model import Annotation, PriorState, Status

# Statuses that cannot be re-mutated by author action (only the auto
# `* → superseded` transition is permitted from these states).
_TERMINAL_STATES: frozenset[Status] = frozenset(
    {Status.ACK, Status.FIXED, Status.DISMISSED}
)


def mutate_status(
    annotation: Annotation,
    new_status: Status,
    *,
    actor: str,
    now: datetime,
    reason: Optional[str] = None,
) -> Annotation:
    """Return a new Annotation with status mutated and the prior state preserved.

    - Records ``dc:modified = now``.
    - Appends a ``PriorState`` snapshot to ``prior_states`` capturing the
      pre-mutation status, creator, and created.
    - When ``reason`` is provided, sets ``dc:description``.
    - Refuses transitions to ``open`` and refuses author-initiated
      transitions out of terminal states (ack/fixed/dismissed).
      The auto ``* → superseded`` transition is always permitted.
    """
    if new_status is Status.OPEN:
        raise ValueError("cannot transition to 'open'; status flows forward only")
    if new_status is not Status.SUPERSEDED and annotation.status in _TERMINAL_STATES:
        raise ValueError(
            f"annotation {annotation.id!r} is already in terminal status "
            f"{annotation.status.value!r}"
        )

    prior = PriorState(
        status=annotation.status,
        creator=annotation.creator,
        created=annotation.created,
    )
    new_prior_states = annotation.prior_states + (prior,)

    description = reason if reason is not None else annotation.description

    return replace(
        annotation,
        status=new_status,
        modified=now,
        modified_by=actor,           # actor recorded here, NOT in creator
        description=description,
        prior_states=new_prior_states,
    )
