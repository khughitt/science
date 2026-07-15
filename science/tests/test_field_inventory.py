"""P0 declare-or-delete instrument: count AUTHORED frontmatter keys per kind."""

from __future__ import annotations

from pathlib import Path

from science_tool.field_inventory import field_inventory


def _write(root: Path, name: str, keys: dict[str, str], *, subdir: str = "hypotheses") -> None:
    directory = root / "entities" / subdir
    directory.mkdir(parents=True, exist_ok=True)
    rendered = "\n".join(f'{key}: "{value}"' for key, value in keys.items())
    (directory / f"{name}.md").write_text(f"---\n{rendered}\n---\n\nbody\n", encoding="utf-8")


def test_counts_authored_keys_only(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "0001-a",
        {"id": "hypothesis:0001-a", "kind": "hypothesis", "title": "T", "status": "proposed", "phase": "active"},
    )
    _write(
        tmp_path,
        "0002-b",
        {"id": "hypothesis:0002-b", "kind": "hypothesis", "title": "T", "status": "proposed"},
    )

    inventory = field_inventory(tmp_path, "hypothesis")

    assert inventory["status"] == 2
    assert inventory["phase"] == 1
    # This reads AUTHORED frontmatter, never the enriched `raw` dict. `_enrich_raw`
    # (graph/sources.py:713) injects these before Pydantic sees a record; declaring them
    # would close the schema around six fields no author has ever written.
    for derived in ("project", "canonical_id", "content_preview", "aliases", "type", "profile"):
        assert derived not in inventory


def test_ignores_other_kinds(tmp_path: Path) -> None:
    _write(tmp_path, "0001-a", {"id": "question:1", "kind": "question", "title": "T"}, subdir="questions")

    assert field_inventory(tmp_path, "hypothesis") == {}


def test_counts_keys_undeclared_on_the_pydantic_model(tmp_path: Path) -> None:
    """The whole point: `Entity` is `extra="ignore"`, so these keys are invisible to every
    consumer that goes through `load_project_sources`. The inventory must see them anyway."""
    _write(
        tmp_path,
        "0001-a",
        {
            "id": "hypothesis:0001-a",
            "kind": "hypothesis",
            "title": "T",
            "required_capabilities": "x",
            "confidence_mechanistic_label": "high",
        },
    )

    inventory = field_inventory(tmp_path, "hypothesis")

    assert inventory["required_capabilities"] == 1
    assert inventory["confidence_mechanistic_label"] == 1


def test_skips_archived_entities(tmp_path: Path) -> None:
    """An archived hypothesis has already had its meaning frozen; it must not widen the
    vocabulary the live schema is closed around."""
    _write(tmp_path, "0001-a", {"id": "hypothesis:0001-a", "kind": "hypothesis", "title": "T"})
    _write(
        tmp_path,
        "0009-old",
        {"id": "hypothesis:0009-old", "kind": "hypothesis", "title": "T", "retired_field": "x"},
        subdir="_archive/hypotheses",
    )

    inventory = field_inventory(tmp_path, "hypothesis")

    assert "retired_field" not in inventory
    assert inventory["id"] == 1


def test_missing_entities_directory_is_empty(tmp_path: Path) -> None:
    assert field_inventory(tmp_path, "hypothesis") == {}
