from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from science_qa.flags import Flag
from science_qa.packs import scrna


class UnknownPackError(Exception):
    """Raised when a config names a pack that is not registered (fail early)."""


PackFn = Callable[[pd.DataFrame, dict], list[Flag]]
PACKS: dict[str, PackFn] = {"scrna": scrna.run}


def resolve_pack(name: str) -> PackFn:
    if name not in PACKS:
        raise UnknownPackError(f"unknown pack {name!r}; known packs: {sorted(PACKS)}")
    return PACKS[name]
