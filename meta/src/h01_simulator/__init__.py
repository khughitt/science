# science:code
# status: library
# task_ids: [t001]
# science:end
"""H01 simulator: stochastic revisiting vs hard gating under noisy evidence."""

from .sweep import build_default_grid, run_single, run_sweep

__all__ = ["build_default_grid", "run_single", "run_sweep"]
