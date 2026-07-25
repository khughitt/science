from __future__ import annotations

import pytest

from science_tool.budget.control import (
    CONTROL_NOTICE_MAX_CHARS,
    bounded_control_notice,
)


def test_control_notice_accepts_a_single_line_at_the_bound() -> None:
    message = "x" * CONTROL_NOTICE_MAX_CHARS
    assert bounded_control_notice(message) == message


def test_control_notice_rejects_dynamic_content_over_the_bound() -> None:
    with pytest.raises(ValueError, match="bounded control notice"):
        bounded_control_notice("x" * (CONTROL_NOTICE_MAX_CHARS + 1))


def test_control_notice_rejects_multiline_payload_shape() -> None:
    with pytest.raises(ValueError, match="single line"):
        bounded_control_notice("wrote 3 rows\npayload leaked")
