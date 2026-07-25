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
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from typing import Literal

from rdflib import Graph, URIRef
from rdflib import Literal as RDFLiteral
from rdflib.namespace import RDF
import yaml
from science_model.entities import Entity

from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.store import PROJECT_NS, SCI_NS


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


def add_skill_load_record_to_graph(record: SkillLoadRecord, graph: Graph) -> None:
    node = skill_load_node_uri(record)
    plan = project_entity_uri(record.plan_id)
    skill = SCI_NS[f"skill/{record.canonical_skill_id}"]
    graph.add((plan, SCI_NS.hasSkillLoad, node))
    graph.add((node, RDF.type, SCI_NS.SkillLoad))
    graph.add((node, SCI_NS.skill, skill))
    graph.add((node, SCI_NS.loadReason, RDFLiteral(record.reason)))
    graph.add((node, SCI_NS.usageSource, RDFLiteral(record.source)))


SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SkillLoadValidationError(ValueError):
    """A `skills_loaded` declaration or the alias table is structurally invalid."""


def _reject_duplicate_keys(node: yaml.Node) -> None:
    # Duplicate detection at the NODE level: yaml.compose builds the node tree without
    # constructing any Python objects (no `!!python/object` risk), so this stays safe while
    # catching a dup key that yaml.safe_load would silently collapse to last-wins.
    if not isinstance(node, yaml.MappingNode):
        return
    seen: set[object] = set()
    # `construct_object`, not `key_node.value`: `.value` is the raw scalar TEXT, so `yes:`
    # and `true:` read as different keys while `yaml.safe_load` resolves both to `True` and
    # collapses them last-wins. Comparing constructed objects catches the YAML-equivalent
    # pairs (`yes`/`true`, `1`/`1.0`, `null`/`~`) that the text does not.
    loader = yaml.SafeLoader("")
    try:
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise SkillLoadValidationError("YAML merge keys are not allowed in skill aliases")
            key = loader.construct_object(key_node, deep=True)
            if key in seen:
                raise SkillLoadValidationError(f"duplicate alias key {key!r}")
            seen.add(key)
    finally:
        loader.dispose()


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


def build_skill_load_records(
    plan_id: str, skills_loaded: object, *, aliases: dict[str, str]
) -> list[SkillLoadRecord]:
    """Validate a plan's `skills_loaded` and produce reified records.

    Raises `SkillLoadValidationError` (a structural error surfaced at the plan
    validation gate) for a malformed shape, a malformed post-alias skill id, or a
    duplicate canonical load. Canonicalization runs through the one shared helper.
    """
    if not isinstance(skills_loaded, list):
        raise SkillLoadValidationError(f"{plan_id}: skills_loaded must be a list")
    records: list[SkillLoadRecord] = []
    seen: dict[str, str] = {}  # canonical id -> the raw id that first produced it
    for item in skills_loaded:
        if not isinstance(item, dict):
            raise SkillLoadValidationError(f"{plan_id}: skills_loaded entry must be a mapping")
        raw_id = item.get("id")
        reason = item.get("reason")
        if not isinstance(raw_id, str) or not raw_id:
            raise SkillLoadValidationError(
                f"{plan_id}: skills_loaded entry needs a non-empty string id"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise SkillLoadValidationError(
                f"{plan_id}: skills_loaded entry {raw_id!r} needs a non-blank string reason"
            )
        canonical = canonicalize_skill_id(raw_id, aliases)
        if canonical in seen:
            raise SkillLoadValidationError(
                f"{plan_id}: duplicate canonical skill load {canonical!r} "
                f"(from {seen[canonical]!r} and {raw_id!r})"
            )
        seen[canonical] = raw_id
        records.append(
            SkillLoadRecord(plan_id=plan_id, canonical_skill_id=canonical, reason=reason)
        )
    return records


def collect_skill_loads(
    entities: Iterable[Entity], *, generation: int | None, aliases: dict[str, str]
) -> list[SkillLoadRecord]:
    """Produce skill-load records for every gen-3 plan carrying `skills_loaded`.

    Gen-≤2 (or unpinned) projects produce nothing — `skills_loaded` there is
    preserved-raw and ignored. Raises `SkillLoadValidationError` on a malformed
    declaration (the structural error surfaces at load, before materialization).
    """
    if generation != 3:
        return []
    records: list[SkillLoadRecord] = []
    for entity in entities:
        if entity.kind != "plan":
            continue
        # `skills_loaded` is preserved-raw in model_extra (Entity is extra="allow"). Test PRESENCE
        # via model_extra, not getattr: an authored `skills_loaded: null` is present-with-value-None
        # and must reach build_skill_load_records to hard-fail, whereas an absent field is skipped.
        extra = entity.model_extra or {}
        if "skills_loaded" not in extra:
            continue
        records.extend(
            build_skill_load_records(entity.canonical_id, extra["skills_loaded"], aliases=aliases)
        )
    return records
