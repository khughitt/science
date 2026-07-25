"""Role-typed, in-memory skill overlay built from the packaged inventory dict.

`science_model` never reads the corpus or the packaged resource: `science_tool`
loads `skill_inventory.json` and passes the dict here. The builder re-validates
the structural invariants (it does not trust an editable resource): malformed
top-level or entry shapes, a duplicate id, an off-catalog or duplicate `covers`
term, a router carrying `covers`, a leaf missing `archetype`, or an invalid
companion is a hard error.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, cast

from science_model.data_products import DataProductCatalog

CompanionRole = Literal["leaf", "router", "index"]
_COMPANION_ROLES: frozenset[str] = frozenset({"leaf", "router", "index"})


class SkillOverlayError(ValueError):
    """The inventory dict violates a role-typing or catalog invariant."""


@dataclass(frozen=True, slots=True)
class Companion:
    target: str
    role: CompanionRole


@dataclass(frozen=True, slots=True)
class LeafSkill:
    id: str
    name: str
    description: str
    archetype: str
    covers: tuple[str, ...]
    sources: tuple[str, ...]
    companions: tuple[Companion, ...]
    role: Literal["leaf"] = "leaf"


@dataclass(frozen=True, slots=True)
class RouterSkill:
    id: str
    name: str
    description: str
    companions: tuple[Companion, ...]
    role: Literal["router"] = "router"


class SkillOverlay:
    """Canonical-id-keyed view over role-typed skills; iterates in id order."""

    def __init__(self, skills: list[LeafSkill | RouterSkill]) -> None:
        self._by_id: dict[str, LeafSkill | RouterSkill] = {}
        for skill in skills:
            if skill.id in self._by_id:
                raise SkillOverlayError(f"duplicate skill id {skill.id!r}")
            self._by_id[skill.id] = skill

    def get(self, skill_id: str) -> LeafSkill | RouterSkill | None:
        return self._by_id.get(skill_id)

    def __contains__(self, skill_id: object) -> bool:
        return skill_id in self._by_id

    def __iter__(self) -> Iterator[LeafSkill | RouterSkill]:
        return (self._by_id[key] for key in sorted(self._by_id))

    def __len__(self) -> int:
        return len(self._by_id)


def _string_tuple(entry: dict, field: str) -> tuple[str, ...]:
    # A present non-list value (for example, `sources: "scanpy"`) is a hard error.
    raw = entry.get(field, [])
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise SkillOverlayError(f"skill {entry['id']!r} {field} must be a list of strings")
    return tuple(raw)


def _required_string(entry: dict, field: str) -> str:
    raw = entry.get(field)
    if not isinstance(raw, str) or not raw:
        raise SkillOverlayError(f"skill entry needs a non-empty string {field}")
    return raw


def _companions(entry: dict) -> tuple[Companion, ...]:
    raw = entry.get("companions", [])
    if not isinstance(raw, list):
        raise SkillOverlayError(
            f"skill {entry['id']!r} companions must be a list of mappings"
        )
    out: list[Companion] = []
    for companion in raw:
        if not isinstance(companion, dict):
            raise SkillOverlayError(
                f"skill {entry['id']!r} companion must be a mapping"
            )
        target = companion.get("target")
        role = companion.get("role")
        if not isinstance(target, str) or not target:
            raise SkillOverlayError(
                f"companion of {entry['id']!r} needs a non-empty string target"
            )
        if not isinstance(role, str) or role not in _COMPANION_ROLES:
            raise SkillOverlayError(f"companion of {entry['id']!r} has unknown role {role!r}")
        out.append(Companion(target=target, role=cast(CompanionRole, role)))
    return tuple(out)


def build_skill_overlay(inventory: dict, catalog: DataProductCatalog) -> SkillOverlay:
    catalog_ids = catalog.by_id
    if not isinstance(inventory, dict):
        raise SkillOverlayError("inventory must be a mapping")
    entries = inventory.get("skills")
    if not isinstance(entries, list):
        raise SkillOverlayError("inventory must contain a 'skills' list")
    skills: list[LeafSkill | RouterSkill] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SkillOverlayError("each inventory skill must be a mapping")
        skill_id = _required_string(entry, "id")
        name = _required_string(entry, "name")
        description = _required_string(entry, "description")
        role = _required_string(entry, "role")
        companions = _companions(entry)
        if role == "router":
            if "covers" in entry or "archetype" in entry:
                raise SkillOverlayError(f"router {skill_id!r} must not carry covers/archetype")
            skills.append(RouterSkill(
                id=skill_id, name=name, description=description,
                companions=companions,
            ))
        elif role == "leaf":
            archetype = _required_string(entry, "archetype")
            covers = _string_tuple(entry, "covers")
            seen: set[str] = set()
            for term in covers:
                if term not in catalog_ids:
                    raise SkillOverlayError(f"leaf {skill_id!r} covers off-catalog term {term!r}")
                if term in seen:
                    raise SkillOverlayError(f"leaf {skill_id!r} has duplicate covers term {term!r}")
                seen.add(term)
            skills.append(LeafSkill(
                id=skill_id, name=name, description=description,
                archetype=archetype, covers=covers,
                sources=_string_tuple(entry, "sources"), companions=companions,
            ))
        else:
            raise SkillOverlayError(f"skill {skill_id!r} has unknown role {role!r}")
    return SkillOverlay(skills)
