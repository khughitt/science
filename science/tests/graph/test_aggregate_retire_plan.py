from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import RetireAction, plan_retirement
from science_tool.graph.aggregate_triage import AggregateBucket, classify_aggregate_rows
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


def test_terms_yaml_cruft_rows_are_planned(tmp_path: Path) -> None:
    # Task 4: terms.yaml is now inside the firewall. A cruft-looking row (migration:audit
    # source_path) in terms.yaml must be planned for deletion when delete_cruft=True.
    _write_entities(tmp_path, [_concept("concept:keep-me")])
    _write_terms(
        tmp_path,
        [{"canonical_id": "concept:in-terms", "kind": "concept", "title": "x", "source_path": "migration:audit"}],
    )
    plan = _plan(tmp_path, promote_coined=True, delete_cruft=True, delete_shadow=True)
    acted = {p.triage.canonical_id for p in (*plan.promote, *plan.delete)}
    assert "concept:in-terms" in acted
    assert "concept:keep-me" in acted


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


def _write_owner_file(root: Path, kind: str, slug: str, cid: str, title: str) -> None:
    """Write a real (non-aggregate) markdown owner file for `cid`."""
    owner_dir = root / "entities" / f"{kind}s"
    owner_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = f"---\nid: {cid}\ntype: {kind}\ntitle: {title}\n---\n\nBody text.\n"
    (owner_dir / f"{slug}.md").write_text(frontmatter, encoding="utf-8")


def test_shadow_row_reconcile_and_delete_interaction(tmp_path: Path) -> None:
    """A SHADOW row appears in reconcile+delete when both promote_coined and delete_shadow
    are set; this double-entry is intentional (marker-gated crash-recovery vs unconditional
    delete). This test pins the behaviour so a future 'dedup the planner' change cannot
    silently break crash-recovery or delete-shadow semantics.
    """
    cid = "concept:1q-gain"
    _write_entities(tmp_path, [_concept(cid)])
    _write_owner_file(tmp_path, "concept", "1q-gain", cid, "1q Gain")

    # Confirm the row classifies as SHADOW before testing the planner.
    sources = _load(tmp_path)
    rows = classify_aggregate_rows(sources)
    row_map = {r.canonical_id: r for r in rows}
    assert cid in row_map, f"{cid!r} not found in triage output"
    assert row_map[cid].bucket is AggregateBucket.SHADOW, (
        f"Expected SHADOW, got {row_map[cid].bucket}; fixture may be wrong"
    )

    owner_path = "entities/concepts/1q-gain.md"

    # With only promote_coined: row is in reconcile (target = owner file), not in delete.
    plan_no_delete = _plan(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    rec_ids = {p.triage.canonical_id for p in plan_no_delete.reconcile}
    del_ids = {p.triage.canonical_id for p in plan_no_delete.delete}
    assert cid in rec_ids, "SHADOW row must appear in reconcile when promote_coined=True"
    assert cid not in del_ids, "SHADOW row must NOT be in delete when delete_shadow=False"
    rec_row = next(p for p in plan_no_delete.reconcile if p.triage.canonical_id == cid)
    assert rec_row.target_path == owner_path, f"reconcile target_path should be owner file, got {rec_row.target_path!r}"

    # With promote_coined + delete_shadow: row appears in BOTH reconcile AND delete.
    plan_both = _plan(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=True)
    rec_ids_both = {p.triage.canonical_id for p in plan_both.reconcile}
    del_ids_both = {p.triage.canonical_id for p in plan_both.delete}
    assert cid in rec_ids_both, "SHADOW row must still appear in reconcile when delete_shadow=True"
    assert cid in del_ids_both, (
        "SHADOW row must also appear in delete when delete_shadow=True (intentional double-entry)"
    )
    del_row = next(p for p in plan_both.delete if p.triage.canonical_id == cid)
    assert del_row.target_path is None, "delete entry must have target_path=None"
