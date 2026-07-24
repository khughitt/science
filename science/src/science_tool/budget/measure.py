"""Deterministic size measurement for budgeted output.

Width is pinned rather than inherited from Rich's non-TTY default, which varies with
``COLUMNS``. Color is excluded: we count ANSI-stripped *visible* characters, so row
selection is identical across color modes. Under ``--color always`` the emitted bytes
exceed the budget by the ANSI overhead -- a human at a terminal, not an agent, and
``resolve_color_policy`` defaults to ``NEVER`` on the agent path.
"""

from __future__ import annotations

import re

BUDGET_CONSOLE_WIDTH = 100

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def visible_len(text: str) -> int:
    """Length of ``text`` with ANSI escape sequences removed."""
    return len(_ANSI_RE.sub("", text))
