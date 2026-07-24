"""Truth path for a plan's `skills_loaded`: validation, canonicalization, and
reified skill-load records materialized into the graph/provenance layer.

Mirrors `dataset_usage.py`: a frozen record with a deterministic content-hash URI.
The record's identity deliberately EXCLUDES `reason` (only `plan_id`,
`canonical_skill_id`, and the categorical `source` participate), so two loads of
the same skill under one plan collide instead of minting two nodes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from importlib import resources
from typing import Literal

from rdflib import URIRef
import yaml

from science_tool.graph.store import PROJECT_NS


@dataclass(frozen=True, slots=True)
class SkillLoadRecord:
    plan_id: str
    canonical_skill_id: str
    reason: str
    # Categorical projection source. Narrowed to the single `UsageSource` value this path emits,
    # so a caller can never mint a second identity for one (plan, skill) load by varying `source`.
    source: Literal["authored"] = "authored"

    def __post_init__(self) -> None:
        if self.source != "authored":
            raise ValueError("source must be 'authored'")

    def identity_payload(self) -> dict[str, str]:
        return {
            "plan_id": self.plan_id,
            "canonical_skill_id": self.canonical_skill_id,
            "source": self.source,
        }

    def payload(self) -> dict[str, str]:
        return {**self.identity_payload(), "reason": self.reason}


def skill_load_node_uri(record: SkillLoadRecord) -> URIRef:
    payload = json.dumps(record.identity_payload(), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return URIRef(PROJECT_NS[f"skill-load/{digest}"])


SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SkillLoadValidationError(ValueError):
    """A `skills_loaded` declaration or the alias table is structurally invalid."""


def _reject_duplicate_keys(node: yaml.Node) -> None:
    # Duplicate detection at the NODE level: yaml.compose builds the node tree without
    # constructing any Python objects (no `!!python/object` risk), so this stays safe while
    # catching a dup key that yaml.safe_load would silently collapse to last-wins.
    if not isinstance(node, yaml.MappingNode):
        return
    seen: set[str] = set()
    for key_node, _ in node.value:
        key = getattr(key_node, "value", None)
        if key in seen:
            raise SkillLoadValidationError(f"duplicate alias key {key!r}")
        seen.add(key)


def _valid_name(value: object) -> bool:
    # fullmatch, not match: `$` matches just before a trailing newline, so `match` would accept
    # `"driver-selection\n"`. fullmatch requires the whole string to be consumed.
    return isinstance(value, str) and SKILL_NAME_RE.fullmatch(value) is not None


def validate_skill_aliases(data: object) -> dict[str, str]:
    if not isinstance(data, dict):
        raise SkillLoadValidationError("skill alias table must be a mapping")
    aliases: dict[str, str] = {}
    for key, value in data.items():
        if not _valid_name(key):
            raise SkillLoadValidationError(f"invalid alias key {key!r} (expected bare skill name)")
        if not _valid_name(value):
            raise SkillLoadValidationError(f"invalid alias target {value!r} for {key!r}")
        aliases[key] = value
    keys = set(aliases)
    for key, value in aliases.items():
        if value in keys:
            raise SkillLoadValidationError(
                f"alias chain: target {value!r} of {key!r} is itself an alias key"
            )
    return aliases


def validate_skill_aliases_yaml(text: str) -> dict[str, str]:
    node = yaml.compose(text, Loader=yaml.SafeLoader)
    if node is not None:
        _reject_duplicate_keys(node)
    # Pass the parsed value through UNCOERCED. `... or {}` would silently turn an empty document,
    # `null`, `[]`, `false`, or `0` into an empty map, hiding a malformed alias table; the mapping
    # check in validate_skill_aliases must see the real value and fail early. The packaged seed is
    # `{}`, so the shipped table always parses to a mapping.
    return validate_skill_aliases(yaml.safe_load(text))


def load_skill_aliases() -> dict[str, str]:
    text = (
        resources.files("science_tool.graph")
        .joinpath("skill_aliases.yaml")
        .read_text(encoding="utf-8")
    )
    return validate_skill_aliases_yaml(text)


def canonicalize_skill_id(raw_id: str, aliases: dict[str, str]) -> str:
    canonical = aliases.get(raw_id, raw_id)
    if not _valid_name(canonical):
        raise SkillLoadValidationError(
            f"invalid skill id {raw_id!r} (post-alias {canonical!r} is not a bare skill name)"
        )
    return canonical
