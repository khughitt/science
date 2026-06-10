from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import apply_retirement, plan_retirement
from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_REQUIRED_FRONTMATTER = ("id", "type", "title", "status", "created", "updated")

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"
_AGG_REL = "knowledge/sources/local/entities.yaml"


def _load(root: Path):
    return load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)


def test_load_plan_apply_reload_resolves_owner_and_shrinks_file(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = tmp_path / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    agg.joinpath("entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "canonical_id": "concept:1q-gain",
                        "kind": "concept",
                        "title": "Chromosome 1q gain",
                        "source_path": _AGG_REL,
                    },
                    {
                        "canonical_id": "concept:cruft",
                        "kind": "concept",
                        "title": "x",
                        "source_path": "migration:audit",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    sources = _load(tmp_path)
    plan = plan_retirement(
        tmp_path, sources, classify_aggregate_rows(sources), promote_coined=True, delete_cruft=True, delete_shadow=False
    )
    apply_retirement(tmp_path, plan, dry_run=False)

    # Owner file exists and the aggregate file is now empty.
    assert (tmp_path / "entities/concepts/1q-gain.md").exists()
    remaining = yaml.safe_load((tmp_path / _AGG_REL).read_text(encoding="utf-8"))["entities"]
    assert remaining == []

    # Reload: the promoted id is now owned by markdown (adapter != aggregate), and no
    # aggregate triage rows remain for it.
    reloaded = _load(tmp_path)
    owner = next(d for d in reloaded.identity_declarations if d.canonical_id == "concept:1q-gain")
    assert owner.adapter != "aggregate"
    triaged_ids = {t.canonical_id for t in classify_aggregate_rows(reloaded)}
    assert "concept:1q-gain" not in triaged_ids
    assert "concept:cruft" not in triaged_ids


def test_promoted_owner_is_frontmatter_conformant(tmp_path: Path) -> None:
    """A promoted coined row yields a file carrying every required frontmatter
    field (entity_conformance._REQUIRED_FRONTMATTER), with created/updated stamped
    from the injected run date and status from the kind default."""
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = tmp_path / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    agg.joinpath("entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "canonical_id": "concept:1q-gain",
                        "kind": "concept",
                        "title": "Chromosome 1q gain",
                        "source_path": _AGG_REL,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    sources = _load(tmp_path)
    plan = plan_retirement(
        tmp_path,
        sources,
        classify_aggregate_rows(sources),
        promote_coined=True,
        delete_cruft=False,
        delete_shadow=False,
    )
    apply_retirement(tmp_path, plan, dry_run=False, today=date(2026, 6, 9))

    owner = tmp_path / "entities/concepts/1q-gain.md"
    fm = yaml.safe_load(owner.read_text(encoding="utf-8").split("---\n", 2)[1])
    for field in _REQUIRED_FRONTMATTER:
        assert field in fm, f"promoted owner missing required field {field!r}"
    assert fm["status"] == "active"  # concept default
    assert fm["created"] == "2026-06-09"
    assert fm["updated"] == "2026-06-09"
