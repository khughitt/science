from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


class Context:
    """Marker base for substrate-typed check inputs.

    Subtypes carry whatever a check needs for that substrate. Only TableContext
    exists today; MatrixContext / SparseExpressionContext land with later substrates.
    """


@dataclass(frozen=True)
class TableContext(Context):
    table: pd.DataFrame
    columns: list[str]  # the resolved column selection a check operates over (may be empty)
