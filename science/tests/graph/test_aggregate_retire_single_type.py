"""Single-type aggregate (doc/<plural>/<plural>.{yaml,json}) retirement (§B5).

Single-type aggregates are, by construction, a list of coined-here owner entities
of one kind (e.g. doc/observations/observations.yaml). They retire to owner files
exactly like multi-type entities.yaml coined rows, id-preserving — observation is a
slug identity kind, so the descriptive ids conform and no inbound refs need rewriting.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import apply_retirement, plan_retirement
from science_tool.graph.aggregate_triage import AggregateBucket, classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"
_OBS_REL = "doc/observations/observations.yaml"


def _load(root: Path):
    return load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)


def _write_obs(root: Path, rows: list[dict]) -> None:
    p = root / "doc" / "observations"
    p.mkdir(parents=True, exist_ok=True)
    p.joinpath("observations.yaml").write_text(yaml.safe_dump(rows, sort_keys=False), encoding="utf-8")


def test_single_type_observation_row_buckets_coined(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    _write_obs(
        tmp_path,
        [{"id": "observation:swan-stage-shift", "title": "SWAN stage shift", "description": "A finding."}],
    )
    rows = classify_aggregate_rows(_load(tmp_path))
    obs = [t for t in rows if t.canonical_id == "observation:swan-stage-shift"]
    assert len(obs) == 1
    assert obs[0].bucket is AggregateBucket.COINED


def test_single_type_observation_promotes_to_owner_file_id_preserving(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    _write_obs(
        tmp_path,
        [
            {
                "id": "observation:swan-stage-shift",
                "title": "SWAN stage shift",
                "description": "Postmenopause shifts lipids net of age.",
                "related": ["hypothesis:0003-menstrual-cycle-systemic-control"],
                "source_refs": ["interpretation:0001-swan-stage-vs-age", "dataset:swan"],
            }
        ],
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
    assert [pr.triage.canonical_id for pr in plan.promote] == ["observation:swan-stage-shift"]

    apply_retirement(tmp_path, plan, dry_run=False, today=date(2026, 6, 10))

    # id-preserving slug owner file at the policy home.
    owner = tmp_path / "entities/observations/swan-stage-shift.md"
    assert owner.exists()
    head, body = owner.read_text(encoding="utf-8").split("---\n", 2)[1:]
    fm = yaml.safe_load(head)
    assert fm["id"] == "observation:swan-stage-shift"
    assert fm["type"] == "observation"
    assert fm["status"] == "active"
    assert fm["created"] == "2026-06-10"
    # reference fields are PRESERVED (load-bearing edges) — not dropped.
    assert fm["related"] == ["hypothesis:0003-menstrual-cycle-systemic-control"]
    assert fm["source_refs"] == ["interpretation:0001-swan-stage-vs-age", "dataset:swan"]
    assert "Postmenopause shifts lipids" in body

    # the emptied single-type aggregate file is removed, not left as an empty list.
    assert not (tmp_path / _OBS_REL).exists()

    # reload: the id is now owned by markdown, no aggregate triage row remains.
    reloaded = _load(tmp_path)
    owner_decl = next(d for d in reloaded.identity_declarations if d.canonical_id == "observation:swan-stage-shift")
    assert owner_decl.adapter != "aggregate"
    assert "observation:swan-stage-shift" not in {t.canonical_id for t in classify_aggregate_rows(reloaded)}


def test_single_type_row_with_real_owner_buckets_shadow(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    _write_obs(
        tmp_path,
        [{"id": "observation:swan-stage-shift", "title": "SWAN stage shift", "description": "A finding."}],
    )
    owner = tmp_path / "entities/observations"
    owner.mkdir(parents=True, exist_ok=True)
    owner.joinpath("swan-stage-shift.md").write_text(
        "---\nid: observation:swan-stage-shift\ntype: observation\ntitle: SWAN stage shift\n"
        "status: active\ncreated: '2026-06-01'\nupdated: '2026-06-01'\n---\n\nOwned.\n",
        encoding="utf-8",
    )
    rows = classify_aggregate_rows(_load(tmp_path))
    obs = [t for t in rows if t.canonical_id == "observation:swan-stage-shift"]
    assert len(obs) == 1
    assert obs[0].bucket is AggregateBucket.SHADOW
