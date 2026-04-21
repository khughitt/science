"""Verdict-token parsing and rollup subsystem.

Implements the 5-token verdict vocabulary plus atomic-claim
decomposition per science-spec:2026-04-19-verdict-tokens-and-atomic-
decomposition-design (v1.1+).
"""

from __future__ import annotations

from science_tool.verdict.tokens import Token, parse_body_verdict

__all__ = ["Token", "parse_body_verdict"]
