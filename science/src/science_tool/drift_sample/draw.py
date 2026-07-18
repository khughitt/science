"""Seeded simple random sample without replacement (design §5).

Equal inclusion probability for every plan. This is what makes the mismatch
count `k` a sufficient statistic, and therefore what makes score.gate()'s
count-based thresholds valid. Any move to unequal `pi` invalidates the gate.
"""

from __future__ import annotations

import random

from science_tool.drift_sample.frame import FrameRow


def draw(frame: list[FrameRow], n: int, seed: int) -> list[FrameRow]:
    ids = [row.plan_id for row in frame]
    if len(ids) != len(set(ids)):
        raise ValueError("frame contains duplicate plan_ids")
    # Sort first so the draw depends only on the seed and the frame's CONTENT,
    # never on enumeration order (filesystem order is not reproducible).
    ordered = sorted(frame, key=lambda r: r.plan_id)
    if n >= len(ordered):
        return ordered
    return random.Random(seed).sample(ordered, n)
