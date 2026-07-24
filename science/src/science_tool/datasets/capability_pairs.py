"""Enumerate distinct raw capability shapes across a corpus, to seed the crosswalk."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

_FIELDS = ("provided_capabilities", "required_capabilities")


@dataclass
class ObservedShape:
    raw: dict[str, str]
    count: int = 0
    example_ids: list[str] = field(default_factory=list)


def enumerate_pairs(records: list[dict]) -> list[ObservedShape]:
    index: dict[tuple[tuple[str, str], ...], ObservedShape] = {}
    for fm in records:
        ident = fm.get("id")
        if not isinstance(ident, str):
            continue
        for name in _FIELDS:
            value = fm.get(name)
            if not isinstance(value, list):
                continue
            for entry in value:
                if not isinstance(entry, Mapping):
                    continue
                raw = {str(k): str(v) for k, v in entry.items()}
                key = tuple(sorted(raw.items()))
                shape = index.setdefault(key, ObservedShape(raw=raw))
                shape.count += 1
                if ident not in shape.example_ids and len(shape.example_ids) < 5:
                    shape.example_ids.append(ident)
    return sorted(index.values(), key=lambda s: (-s.count, tuple(sorted(s.raw.items()))))
