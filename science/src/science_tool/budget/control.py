"""Bound the sole non-payload message emitted after a file-sink flush."""

from __future__ import annotations

from science_tool.budget.measure import visible_len

# A platform-usable filesystem path is normally bounded near 4 KiB. Twice that leaves
# room for the fixed sentence and a decimal count while remaining well below the
# smallest 20,000-character payload ceiling.
CONTROL_NOTICE_MAX_CHARS = 8_192


def bounded_control_notice(message: str) -> str:
    """Validate the fixed-shape, single-line control notice."""
    if "\n" in message or "\r" in message:
        raise ValueError("a bounded control notice must be a single line")
    size = visible_len(message)
    if size > CONTROL_NOTICE_MAX_CHARS:
        raise ValueError(
            f"bounded control notice is {size} visible chars, over its "
            f"{CONTROL_NOTICE_MAX_CHARS} ceiling"
        )
    return message
