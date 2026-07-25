"""Strict parsing for packaged skill frontmatter."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from importlib import resources
from pathlib import Path

import yaml

from science_model.data_products import DataProductCatalog

from science_tool.graph.skill_loads import SKILL_NAME_RE


class SkillInventoryError(ValueError):
    """The skills corpus, INDEX, or a skill's frontmatter is structurally invalid."""


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _reject_dup_and_merge_keys(node: yaml.Node) -> None:
    if isinstance(node, yaml.MappingNode):
        seen: set[object] = set()
        loader = yaml.SafeLoader("")
        try:
            for key_node, value_node in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    raise SkillInventoryError("YAML merge keys are not allowed in skill frontmatter")
                key = loader.construct_object(key_node, deep=True)
                if key in seen:
                    raise SkillInventoryError(f"duplicate frontmatter key {key!r}")
                seen.add(key)
                _reject_dup_and_merge_keys(value_node)
        finally:
            loader.dispose()
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            _reject_dup_and_merge_keys(item)


def parse_skill_frontmatter(text: str) -> dict:
    """Return the YAML mapping in a skill document's opening frontmatter block."""
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise SkillInventoryError("missing frontmatter block")

    block = match.group(1)
    node = yaml.compose(block, Loader=yaml.SafeLoader)
    if node is not None:
        _reject_dup_and_merge_keys(node)

    data = yaml.safe_load(block)
    if not isinstance(data, dict):
        raise SkillInventoryError("frontmatter is not a mapping")
    return data


_INDEX_LINE_RE = re.compile(r"^\s*-\s*`([^`]+)`:\s*`(skills/[^`]+)`", re.MULTILINE)


def real_skill_paths(repo_root: Path) -> set[str]:
    out: set[str] = set()
    for path in (repo_root / "skills").rglob("*.md"):
        rel = path.relative_to(repo_root).as_posix()
        if rel == "skills/INDEX.md" or rel.startswith("skills/meta/templates/"):
            continue
        out.add(rel)
    return out


def load_index_registry(repo_root: Path) -> list[tuple[str, str]]:
    index_text = (repo_root / "skills" / "INDEX.md").read_text(encoding="utf-8")
    entries = _INDEX_LINE_RE.findall(index_text)
    ids: set[str] = set()
    paths: set[str] = set()
    for sid, rel in entries:
        if SKILL_NAME_RE.fullmatch(sid) is None:
            raise SkillInventoryError(f"INDEX id {sid!r} fails the canonical skill-id grammar")
        if sid in ids:
            raise SkillInventoryError(f"duplicate INDEX id {sid!r}")
        if rel in paths:
            raise SkillInventoryError(f"duplicate INDEX path {rel!r}")
        if not (repo_root / rel).is_file():
            raise SkillInventoryError(f"INDEX path {rel!r} does not exist")
        ids.add(sid)
        paths.add(rel)
    real = real_skill_paths(repo_root)
    orphan = real - paths
    if orphan:
        raise SkillInventoryError(f"real skills missing from INDEX: {sorted(orphan)}")
    extra = paths - real
    if extra:
        raise SkillInventoryError(f"INDEX lists paths that are not a real skill: {sorted(extra)}")
    return entries


_COMPANION_SECTION_RE = re.compile(
    r"^## Companion Skills\s*$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
)
_LINK_TARGET_RE = re.compile(r"\]\(([^)]+)\)")


def companion_section(text: str) -> str:
    match = _COMPANION_SECTION_RE.search(text)
    return match.group(1) if match else ""


def resolve_companions(
    repo_root: Path, skill_rel_path: str, section: str, path_to_id: dict[str, str]
) -> list[dict]:
    root = repo_root.resolve()
    skill_abs = root / skill_rel_path
    edges: list[dict] = []
    seen: set[str] = set()
    for target in _LINK_TARGET_RE.findall(section):
        raw = target.split()[0].split("#")[0]
        if not raw:
            continue
        resolved = (skill_abs.parent / raw).resolve()
        try:
            rel = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise SkillInventoryError(
                f"{skill_rel_path}: companion target {raw!r} escapes the repo"
            ) from exc
        if rel == "skills/INDEX.md":
            target_id, role = "science-skill-index", "index"
        elif rel in path_to_id:
            target_id = path_to_id[rel]
            role = "router" if resolved.name == "SKILL.md" else "leaf"
        else:
            raise SkillInventoryError(
                f"{skill_rel_path}: companion target {raw!r} resolves to non-skill {rel!r}"
            )
        if target_id in seen:
            raise SkillInventoryError(
                f"{skill_rel_path}: duplicate companion target {target_id!r}"
            )
        seen.add(target_id)
        edges.append({"target": target_id, "role": role})
    return edges


def _optional_string_list(rel: str, frontmatter: dict, field: str) -> list[str]:
    # Presence-aware, NOT truthiness-aware: an ABSENT field yields []. A PRESENT field must be a
    # list of strings — an authored `covers: null` / `sources: null` is present-with-value-None and
    # hard-fails here (fail early), rather than being silently read as "omitted".
    if field not in frontmatter:
        return []
    raw = frontmatter[field]
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise SkillInventoryError(f"{rel}: {field} must be a list of strings")
    return list(raw)


def _validate_covers(rel: str, frontmatter: dict, catalog_ids: Mapping[str, object]) -> list[str]:
    terms = _optional_string_list(rel, frontmatter, "covers")
    seen: set[str] = set()
    for term in terms:
        if term not in catalog_ids:
            raise SkillInventoryError(f"{rel}: covers term {term!r} is not in the data-product catalog")
        if term in seen:
            raise SkillInventoryError(f"{rel}: duplicate covers term {term!r}")
        seen.add(term)
    return terms


def build_skill_inventory(repo_root: Path, catalog: DataProductCatalog) -> dict:
    entries = load_index_registry(repo_root)
    path_to_id = {rel: sid for sid, rel in entries}
    catalog_ids = catalog.by_id
    skills: list[dict] = []
    for sid, rel in entries:
        path = repo_root / rel
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_skill_frontmatter(text)
        name = frontmatter.get("name")
        if not isinstance(name, str) or not name:
            raise SkillInventoryError(f"{rel}: frontmatter is missing a string name")
        description = frontmatter.get("description")
        if not isinstance(description, str) or not description:
            raise SkillInventoryError(f"{rel}: frontmatter is missing a string description")
        role = "router" if path.name == "SKILL.md" else "leaf"
        entry: dict = {"id": sid, "name": name, "path": rel, "role": role, "description": description}
        if role == "router":
            if "archetype" in frontmatter:
                raise SkillInventoryError(f"{rel}: a router must not declare archetype")
            if "covers" in frontmatter:
                raise SkillInventoryError(f"{rel}: a router must not declare covers")
        else:
            archetype = frontmatter.get("archetype")
            if not isinstance(archetype, str) or not archetype:
                raise SkillInventoryError(f"{rel}: a leaf must declare a string archetype")
            entry["archetype"] = archetype
            covers = _validate_covers(rel, frontmatter, catalog_ids)
            if covers:
                entry["covers"] = covers
            sources = _optional_string_list(rel, frontmatter, "sources")
            if sources:
                entry["sources"] = sources
        companions = resolve_companions(repo_root, rel, companion_section(text), path_to_id)
        if companions:
            entry["companions"] = companions
        skills.append(entry)
    skills.sort(key=lambda item: item["id"])
    return {"skills": skills}


def serialize_inventory(inventory: dict) -> str:
    return json.dumps(inventory, indent=2, sort_keys=True) + "\n"


_RESOURCE_NAME = "skill_inventory.json"


def load_skill_inventory() -> dict:
    text = (
        resources.files("science_tool.graph")
        .joinpath(_RESOURCE_NAME)
        .read_text(encoding="utf-8")
    )
    data = json.loads(text)
    # Fail early on a malformed resource: a missing/non-list `skills` must NOT degrade into an
    # empty corpus (which would masquerade as "no covering skills" downstream in sub-plan 4).
    if not isinstance(data, dict) or not isinstance(data.get("skills"), list):
        raise SkillInventoryError("skill_inventory.json must be a mapping with a 'skills' list")
    return data
