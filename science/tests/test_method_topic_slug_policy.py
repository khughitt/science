# tests/test_method_topic_slug_policy.py
from __future__ import annotations

from pathlib import Path

from science_tool.entities import (
    generate_entity_id,
    local_part_conforms,
    resolve_path_policy,
)


def test_method_and_topic_use_slug_strategy(tmp_path: Path) -> None:
    assert resolve_path_policy("method", project_root=tmp_path).strategy == "slug"
    assert resolve_path_policy("topic", project_root=tmp_path).strategy == "slug"


def test_slug_local_part_conforms_for_method_and_topic(tmp_path: Path) -> None:
    # The MM30-shaped coined ids: lowercase slug local parts.
    assert local_part_conforms("method", "bayesian-inference", project_root=tmp_path)
    assert local_part_conforms("topic", "proliferation-dominance", project_root=tmp_path)


def test_legacy_numeric_local_part_still_conforms(tmp_path: Path) -> None:
    # Broadening, not invalidating: a numeric-shaped id still satisfies the slug regex.
    assert local_part_conforms("method", "0001-foo", project_root=tmp_path)


def test_generated_method_id_is_slug_derived(tmp_path: Path) -> None:
    # Forward consequence: new method ids are slug-derived, not NNNN-.
    # generate_entity_id(project_root, kind, title, entity_id, slug, today=None).
    new_id = generate_entity_id(tmp_path, "method", "Bayesian Inference", None, None)
    assert new_id.startswith("method:")
    local = new_id.split(":", 1)[1]
    # slug shape: lowercase, hyphen-separated, no leading digits-only sequence prefix.
    assert local == "bayesian-inference"
    assert local_part_conforms("method", local, project_root=tmp_path)
