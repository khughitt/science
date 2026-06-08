from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import RetireAction, plan_retirement
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"


def _write_entities(root: Path, entries: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def _write_terms(root: Path, entries: list[dict]) -> None:
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "terms.yaml").write_text(yaml.safe_dump({"terms": entries}), encoding="utf-8")


def _concept(cid: str) -> dict:
    return {
        "canonical_id": cid,
        "kind": "concept",
        "title": cid,
        "source_path": "knowledge/sources/local/entities.yaml",
    }


def _cruft(cid: str, kind: str) -> dict:
    return {"canonical_id": cid, "kind": kind, "title": cid, "source_path": "migration:audit"}


def _load(root: Path):
    return load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)


def _plan(root: Path, **flags):
    sources = _load(root)
    from science_tool.graph.aggregate_triage import classify_aggregate_rows

    return plan_retirement(root, sources, classify_aggregate_rows(sources), **flags)


def test_coined_promotes_with_policy_target(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_concept("concept:1q-gain")])
    plan = _plan(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert [p.triage.canonical_id for p in plan.promote] == ["concept:1q-gain"]
    row = plan.promote[0]
    assert row.action is RetireAction.PROMOTE
    assert row.target_path == "entities/concepts/1q-gain.md"
    assert row.source_path == "knowledge/sources/local/entities.yaml"
    assert row.line is not None


def test_cruft_deletes_only_when_enabled(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_cruft("concept:treatment-benefit", "concept")])
    off = _plan(tmp_path, promote_coined=False, delete_cruft=False, delete_shadow=False)
    assert off.delete == ()
    on = _plan(tmp_path, promote_coined=False, delete_cruft=True, delete_shadow=False)
    assert [p.triage.canonical_id for p in on.delete] == ["concept:treatment-benefit"]


def test_terms_yaml_rows_are_never_planned(tmp_path: Path) -> None:
    # A coined/cruft-looking row in terms.yaml must be excluded by the firewall.
    _write_entities(tmp_path, [_concept("concept:keep-me")])
    _write_terms(
        tmp_path,
        [{"canonical_id": "concept:in-terms", "kind": "concept", "title": "x", "source_path": "migration:audit"}],
    )
    plan = _plan(tmp_path, promote_coined=True, delete_cruft=True, delete_shadow=True)
    acted = {p.triage.canonical_id for p in (*plan.promote, *plan.delete)}
    assert "concept:in-terms" not in acted
    assert acted == {"concept:keep-me"}


def test_ambiguous_rows_are_never_acted(tmp_path: Path) -> None:
    # A self-sourced `topic` buckets AMBIGUOUS (a never-acted bucket). Even with all
    # three flags on, it must be neither promoted nor deleted.
    _write_entities(
        tmp_path,
        [
            {
                "canonical_id": "topic:some-topic",
                "kind": "topic",
                "title": "x",
                "source_path": "knowledge/sources/local/entities.yaml",
            }
        ],
    )
    plan = _plan(tmp_path, promote_coined=True, delete_cruft=True, delete_shadow=True)
    assert plan.promote == ()
    assert plan.delete == ()


def test_slug_id_failing_conformance_is_rejected_not_promoted(tmp_path: Path) -> None:
    # A coined `concept` (slug kind) whose local part is not a valid slug (underscore)
    # must be REJECTED by conformance, never promoted into a policy-violating file.
    # (canonical_id has no load-time format validator, so the row reaches the planner.)
    _write_entities(
        tmp_path,
        [
            {
                "canonical_id": "concept:bad_slug",
                "kind": "concept",
                "title": "x",
                "source_path": "knowledge/sources/local/entities.yaml",
            }
        ],
    )
    plan = _plan(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert plan.promote == ()
    assert any(t.canonical_id == "concept:bad_slug" for t, _ in plan.rejected)
