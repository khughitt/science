"""Adaptive rotation: rank a project's reviewable corpus least-recently-reviewed
first and compute this sweep's adaptive budget. Stateless and read-only."""

from __future__ import annotations

import math
from datetime import date

ROTATION_A = 12.57
ROTATION_B = 11.53
N_FULL = 25

DATE_MIN = date.min


def rotation_budget(pool_size: int) -> int:
    """Per-sweep budget n(N). Full-read up to N_FULL, then a sublinear taper,
    clamped to [1, pool_size]; 0 for an empty corpus."""
    if pool_size < 0:
        raise ValueError(f"pool_size must be non-negative, got {pool_size}")
    if pool_size <= N_FULL:
        return pool_size  # covers 0..N_FULL, so n(0)=0
    raw = math.ceil(ROTATION_B * math.log(pool_size) - ROTATION_A)
    return min(pool_size, max(1, raw))
