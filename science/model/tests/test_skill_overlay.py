from __future__ import annotations

import pytest

from science_model.data_products import build_catalog
from science_model.skill_coverage import (
    LeafSkill,
    RouterSkill,
    SkillOverlayError,
    build_skill_overlay,
)


def _catalog():
    return build_catalog({
        "schema_version": "1",
        "terms": [{"id": "data-product:somatic-variant", "label": "SNV", "assay": "dna"}],
    })


def _inv(skills):
    return {"skills": skills}


def test_build_overlay_role_typing() -> None:
    overlay = build_skill_overlay(_inv([
        {"id": "bio", "name": "bio", "path": "skills/bio/SKILL.md", "role": "router",
         "description": "r", "companions": [{"target": "somatic", "role": "leaf"}]},
        {"id": "somatic", "name": "display-somatic", "path": "skills/somatic.md", "role": "leaf",
         "description": "d", "archetype": "measurement-qa",
         "covers": ["data-product:somatic-variant"]},
    ]), _catalog())
    router = overlay.get("bio")
    assert isinstance(router, RouterSkill)
    assert router.companions[0].target == "somatic" and router.companions[0].role == "leaf"
    leaf = overlay.get("somatic")
    assert isinstance(leaf, LeafSkill)
    assert leaf.id == "somatic" and leaf.name == "display-somatic"  # INDEX id is the key
    assert leaf.covers == ("data-product:somatic-variant",)
    assert leaf.sources == ()  # omitted -> empty
    assert [s.id for s in overlay] == ["bio", "somatic"]  # id order
    assert "somatic" in overlay and len(overlay) == 2


def test_build_overlay_rejects_duplicate_id() -> None:
    with pytest.raises(SkillOverlayError, match="duplicate"):
        build_skill_overlay(_inv([
            {"id": "x", "name": "x", "path": "skills/x.md", "role": "leaf",
             "description": "d", "archetype": "a"},
            {"id": "x", "name": "x2", "path": "skills/x2.md", "role": "leaf",
             "description": "d", "archetype": "a"},
        ]), _catalog())


def test_build_overlay_rejects_off_catalog_cover() -> None:
    with pytest.raises(SkillOverlayError, match="catalog"):
        build_skill_overlay(_inv([
            {"id": "x", "name": "x", "path": "skills/x.md", "role": "leaf",
             "description": "d", "archetype": "a", "covers": ["data-product:ghost"]},
        ]), _catalog())


def test_build_overlay_rejects_router_with_empty_covers() -> None:
    with pytest.raises(SkillOverlayError, match="router"):
        build_skill_overlay(_inv([
            {"id": "r", "name": "r", "path": "skills/SKILL.md", "role": "router",
             "description": "d", "covers": []},
        ]), _catalog())


def test_build_overlay_rejects_duplicate_covers() -> None:
    with pytest.raises(SkillOverlayError, match="duplicate"):
        build_skill_overlay(_inv([
            {"id": "x", "name": "x", "path": "skills/x.md", "role": "leaf",
             "description": "d", "archetype": "a",
             "covers": ["data-product:somatic-variant", "data-product:somatic-variant"]},
        ]), _catalog())


def test_build_overlay_rejects_non_list_sources() -> None:
    with pytest.raises(SkillOverlayError, match="sources"):
        build_skill_overlay(_inv([
            {"id": "x", "name": "x", "path": "skills/x.md", "role": "leaf",
             "description": "d", "archetype": "a", "sources": "scanpy"},
        ]), _catalog())


def test_build_overlay_rejects_leaf_without_archetype() -> None:
    with pytest.raises(SkillOverlayError, match="archetype"):
        build_skill_overlay(_inv([
            {"id": "x", "name": "x", "path": "skills/x.md", "role": "leaf", "description": "d"},
        ]), _catalog())


def test_build_overlay_rejects_unknown_companion_role() -> None:
    with pytest.raises(SkillOverlayError, match="role"):
        build_skill_overlay(_inv([
            {"id": "r", "name": "r", "path": "skills/SKILL.md", "role": "router", "description": "d",
             "companions": [{"target": "x", "role": "sibling"}]},
        ]), _catalog())


def test_build_overlay_rejects_missing_skills_list() -> None:
    with pytest.raises(SkillOverlayError, match="skills"):
        build_skill_overlay({}, _catalog())
