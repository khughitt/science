"""Load the value->term crosswalk (strict contract, adjudicated dispositions)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

_DISPOSITIONS = {"drop", "refuse"}
_MAPPING_KEYS = {"match", "data_product", "qualifiers", "out_of_scope"}


class CrosswalkError(ValueError):
    """The crosswalk is invalid, or a raw capability shape is unmapped."""


@dataclass(frozen=True)
class Mapped:
    capability: dict


@dataclass(frozen=True)
class Dropped:
    rationale: str


@dataclass(frozen=True)
class Refused:
    rationale: str


RewriteResult = Mapped | Dropped | Refused


@dataclass(frozen=True)
class _Entry:
    data_product: str | None
    qualifiers: dict[str, str]
    disposition: str | None
    rationale: str


@dataclass
class Crosswalk:
    _by_match: dict[tuple[tuple[str, str], ...], _Entry]

    @staticmethod
    def _key(raw: Mapping) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((str(k), str(v)) for k, v in raw.items()))

    @classmethod
    def load(cls, path: Path, *, catalog_ids: set[str]) -> "Crosswalk":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if data.get("schema_version") != "1":
            raise CrosswalkError(f"schema_version must be '1', got {data.get('schema_version')!r}")
        mappings = data.get("mappings")
        if not isinstance(mappings, list) or not mappings:
            raise CrosswalkError("mappings must be a non-empty list")
        by_match: dict[tuple[tuple[str, str], ...], _Entry] = {}
        for m in mappings:
            if not isinstance(m, Mapping) or set(m) - _MAPPING_KEYS:
                raise CrosswalkError(f"mapping has unknown or missing keys: {m!r}")
            match = m.get("match")
            if not isinstance(match, Mapping) or not match:
                raise CrosswalkError(f"mapping needs a non-empty match: {m!r}")
            key = cls._key(match)
            if key in by_match:
                raise CrosswalkError(f"duplicate match {dict(match)!r}")
            has_dp = "data_product" in m
            has_oos = "out_of_scope" in m
            if has_dp == has_oos:
                raise CrosswalkError(f"mapping {dict(match)!r} needs exactly one of data_product / out_of_scope")
            if has_dp:
                dp = m["data_product"]
                if not isinstance(dp, str) or dp not in catalog_ids:
                    raise CrosswalkError(f"mapping {dict(match)!r} data_product {dp!r} absent from catalog")
                quals = m.get("qualifiers", {})
                if not _valid_quals(quals):
                    raise CrosswalkError(f"mapping {dict(match)!r} qualifiers must be non-empty str->str")
                by_match[key] = _Entry(dp, dict(quals), None, "")
            else:
                oos = m["out_of_scope"]
                if not isinstance(oos, Mapping) or set(oos) - {"disposition", "rationale"}:
                    raise CrosswalkError(f"mapping {dict(match)!r} out_of_scope must be {{disposition, rationale}}")
                disp, rat = oos.get("disposition"), oos.get("rationale")
                if disp not in _DISPOSITIONS or not isinstance(rat, str) or not rat.strip():
                    raise CrosswalkError(f"mapping {dict(match)!r} needs disposition in {_DISPOSITIONS} + rationale")
                by_match[key] = _Entry(None, {}, disp, rat.strip())
        return cls(_by_match=by_match)

    def rewrite(self, entry: Mapping) -> RewriteResult:
        found = self._by_match.get(self._key(entry))
        if found is None:
            raise CrosswalkError(f"no crosswalk entry for raw capability {dict(entry)!r}")
        if found.disposition == "drop":
            return Dropped(found.rationale)
        if found.disposition == "refuse":
            return Refused(found.rationale)
        return Mapped({"data_product": found.data_product, "qualifiers": dict(found.qualifiers)})


def _valid_quals(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    return all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
               for k, v in value.items())
