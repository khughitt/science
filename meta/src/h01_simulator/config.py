"""Dataclass configs and result records for the h01 simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

PolicyKind = Literal["hard_gate", "constant_revisit", "thompson"]
BiasModel = Literal["none", "independent", "shared"]

_ALLOWED_KINDS = {"hard_gate", "constant_revisit", "thompson"}
_ALLOWED_BIAS_MODELS = {"none", "independent", "shared"}


@dataclass(frozen=True)
class SimConfig:
    """Parameters of one simulator run.

    Bias semantics:
      - ``bias_model == "none"``: no bias applied; ``bias_fraction`` and
        ``bias_sigma`` are ignored.
      - ``bias_model == "independent"``: each proposition in a randomly
        chosen subset of size ``round(bias_fraction * n_propositions)``
        receives an iid offset drawn from ``Normal(0, bias_sigma)`` at run
        start.
      - ``bias_model == "shared"``: a single offset ``delta ~ Normal(0,
        bias_sigma)`` is drawn once per run and applied to every proposition
        in the biased subset. This is the H01 disputing-evidence mode.
    """

    n_propositions: int
    budget: int
    p_pos: float
    p_neg: float
    prior_true: float
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    bias_model: BiasModel = "none"
    bias_fraction: float = 0.0
    bias_sigma: float = 0.0
    seed: int = 0

    def __post_init__(self) -> None:
        for name in ("p_pos", "p_neg", "prior_true", "bias_fraction"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {v}")
        if self.p_pos <= self.p_neg:
            raise ValueError(f"p_pos ({self.p_pos}) must exceed p_neg ({self.p_neg})")
        if self.n_propositions <= 0 or self.budget <= 0:
            raise ValueError("n_propositions and budget must be positive")
        if self.prior_alpha <= 0.0 or self.prior_beta <= 0.0:
            raise ValueError("prior_alpha and prior_beta must be positive")
        if self.bias_sigma < 0.0:
            raise ValueError(f"bias_sigma must be non-negative, got {self.bias_sigma}")
        if self.bias_model not in _ALLOWED_BIAS_MODELS:
            raise ValueError(f"unknown bias_model: {self.bias_model}")


@dataclass(frozen=True)
class PolicyConfig:
    """Parameters of one allocation policy."""

    kind: PolicyKind
    warmup_actions: int = 1
    gate_threshold: float = 0.3
    revisit_prob: float = 0.0

    def __post_init__(self) -> None:
        if self.kind not in _ALLOWED_KINDS:
            raise ValueError(f"unknown policy kind: {self.kind}")
        if not 0.0 <= self.revisit_prob <= 1.0:
            raise ValueError(f"revisit_prob must be in [0, 1], got {self.revisit_prob}")
        if self.warmup_actions <= 0:
            raise ValueError(f"warmup_actions must be positive, got {self.warmup_actions}")
        if not 0.0 < self.gate_threshold < 1.0:
            raise ValueError(
                f"gate_threshold must be in (0, 1), got {self.gate_threshold}"
            )


@dataclass
class RunResult:
    """Result of one simulator run."""

    config: SimConfig
    policy: PolicyConfig
    recall: float
    brier: float
    regret: float
    allocations: np.ndarray
    final_posteriors: np.ndarray
    ground_truth: np.ndarray
    bias_offsets: np.ndarray
