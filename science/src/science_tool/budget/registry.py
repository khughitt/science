"""Single source of truth for per-command output ceilings and payload shapes.

Ceilings are in *visible* characters (ANSI stripped) at ``BUDGET_CONSOLE_WIDTH``. Values
come from the 2026-07-24 audit of ``~/d/natural-systems``, the largest adopting project.

Three tables, deliberately distinct:

- ``BUDGETS``   -- wired: the command owns a sink and honours a ceiling.
- ``EXEMPTIONS``-- a claim that the command's output CANNOT grow with project size.
- ``DEFERRED``  -- CAN grow with project size, not yet wired.

``DEFERRED`` is defined by growability, not by current size. An earlier draft required a
measurement above 20k, which left no truthful home for a command that grows but happens
to be small today -- ``tasks archive`` emits one row per archivable task
(``tasks_cli.py:333``) yet measures tiny on a freshly-archived project. Calling that
exempt would assert something false. Every non-budgeted command therefore carries a
justification string either way: ``EXEMPTIONS`` says why it cannot grow, ``DEFERRED``
says what makes it grow.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PayloadShape(StrEnum):
    """How a command's payload may be narrowed.

    ``ROWS``     -- a flat row list; project by dropping rows.
    ``REPORT``   -- a heterogeneous multi-section report; project per section.
    ``DOCUMENT`` -- a versioned document; REFUSE past budget, never partially emit.
    """

    ROWS = "rows"
    REPORT = "report"
    DOCUMENT = "document"


@dataclass(frozen=True)
class CommandBudget:
    max_chars: int
    shape: PayloadShape
    max_rows: int | None = None


@dataclass(frozen=True)
class DeferredCommand:
    """A command whose output grows with project size but is not yet wired.

    ``growth_reason`` states WHAT makes it grow -- the mirror of an exemption's reason.
    ``measured_chars`` records an observation, not a threshold for admission.
    """

    growth_reason: str
    target_slice: str
    measured_chars: int | None = None


BUDGETS: dict[str, CommandBudget] = {
    "tasks list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "health": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "entities inventory": CommandBudget(max_chars=20_000, shape=PayloadShape.DOCUMENT),
    "data audit": CommandBudget(max_chars=20_000, shape=PayloadShape.DOCUMENT),
}

EXEMPTIONS: dict[str, str] = {
    "tasks summary": "measured 1,692 chars on 2026-07-24; aggregate counts, cannot grow with backlog size",
    "graph stats": "measured 341 chars on 2026-07-24; fixed-shape summary",
    "telemetry status": "measured 366 chars on 2026-07-24; fixed-shape summary",
}

DEFERRED: dict[str, DeferredCommand] = {
    # Measured over budget on 2026-07-24; wiring scheduled for slice 1b.
    "entity list": DeferredCommand("one row per entity", "1b", 1_706_994),
    "curate inventory": DeferredCommand("one record per entity", "1b", 683_657),
    "prose lint": DeferredCommand("one row per prose finding", "1b", 550_226),
    "questions list": DeferredCommand("one row per question", "1b", 113_076),
    "validate": DeferredCommand("one row per validation finding", "1b", 109_466),
    "interpretations list": DeferredCommand("one row per interpretation", "1b", 97_281),
    "curate consolidation-candidates": DeferredCommand("one row per candidate cluster", "1b", 71_553),
    "entity needs-review": DeferredCommand("one row per flagged entity", "1b", 59_697),
    "feedback list": DeferredCommand("one row per feedback item", "1b", 44_307),
    "discussions list": DeferredCommand("one row per discussion", "1b", 30_780),
    # Growable but small on the audited project -- the case that has no truthful
    # exemption. Populated further by Task 13 Step 3.
    "tasks archive": DeferredCommand("one row per archivable task", "1b"),
}


def lookup(command_path: str) -> CommandBudget | None:
    return BUDGETS.get(command_path)


def shape_for(command_path: str) -> PayloadShape | None:
    budget = BUDGETS.get(command_path)
    return budget.shape if budget is not None else None
