"""Budget-formula boundary tests for adaptive rotation."""

from __future__ import annotations

import pytest

from science_tool.curate.rotation import rotation_budget


@pytest.mark.parametrize(
    ("pool_size", "expected"),
    [
        (0, 0),
        (1, 1),
        (25, 25),   # N_FULL: full read
        (26, 25),   # first tapered value, < 26
        (100, 41),
        (389, 57),  # calibration anchor; ceil(389/57) == 7 sweeps
    ],
)
def test_rotation_budget_anchors(pool_size: int, expected: int) -> None:
    assert rotation_budget(pool_size) == expected


def test_rotation_budget_never_exceeds_pool() -> None:
    for n in range(0, 400):
        assert 0 <= rotation_budget(n) <= n or n == 0


def test_rotation_budget_monotone_nondecreasing() -> None:
    values = [rotation_budget(n) for n in range(1, 400)]
    assert all(b <= a for b, a in zip(values, values[1:]))


def test_rotation_budget_negative_raises() -> None:
    with pytest.raises(ValueError):
        rotation_budget(-5)
