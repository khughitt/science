from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import (
    PlannedRow,
    RetireAction,
    RetirementPlan,
    apply_retirement,
    plan_retirement,
)
from science_tool.graph.aggregate_triage import AggregateBucket, AggregateRowTriage, classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"
_AGG_REL = "knowledge/sources/local/entities.yaml"


def _write_entities(root: Path, entries: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def _concept(cid: str, title: str = "x") -> dict:
    return {"canonical_id": cid, "kind": "concept", "title": title, "source_path": _AGG_REL}


def _cruft(cid: str) -> dict:
    return {"canonical_id": cid, "kind": "concept", "title": "x", "source_path": "migration:audit"}


def _entities_on_disk(root: Path) -> list[str]:
    data = yaml.safe_load((root / _AGG_REL).read_text(encoding="utf-8")) or {}
    return [e["canonical_id"] for e in data.get("entities") or []]


def _run(root: Path, *, dry_run: bool, **flags):
    sources = load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)
    plan = plan_retirement(root, sources, classify_aggregate_rows(sources), **flags)
    return apply_retirement(root, plan, dry_run=dry_run)


def test_promote_writes_owner_preserving_id_and_drops_entry(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_concept("concept:1q-gain", "Chromosome 1q gain"), _concept("concept:age", "Age")])
    report = _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert set(report.promoted) == {"concept:1q-gain", "concept:age"}
    owner = tmp_path / "entities/concepts/1q-gain.md"
    assert owner.exists()
    fm = yaml.safe_load(owner.read_text(encoding="utf-8").split("---")[1])
    assert fm["id"] == "concept:1q-gain"
    assert fm["kind"] == "concept"
    assert fm["title"] == "Chromosome 1q gain"
    assert fm["promoted_from"] == _AGG_REL
    assert _entities_on_disk(tmp_path) == []  # both promoted out


def test_delete_cruft_removes_entry_no_owner(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_concept("concept:keep"), _cruft("concept:drop")])
    report = _run(tmp_path, dry_run=False, promote_coined=False, delete_cruft=True, delete_shadow=False)
    assert report.deleted == ("concept:drop",)
    assert _entities_on_disk(tmp_path) == ["concept:keep"]
    assert not (tmp_path / "entities/concepts/drop.md").exists()  # delete never writes an owner


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_concept("concept:1q-gain")])
    report = _run(tmp_path, dry_run=True, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert report.dry_run is True
    assert report.promoted == ("concept:1q-gain",)
    assert not (tmp_path / "entities/concepts/1q-gain.md").exists()
    assert _entities_on_disk(tmp_path) == ["concept:1q-gain"]


def test_missing_title_is_rejected_entry_retained(tmp_path: Path) -> None:
    # The loader VALIDATES entities before emitting metadata (Entity.title is required),
    # so a title-less row is skipped at load and never reaches the planner. The executor's
    # missing-field guard reads the RAW entry, so drive it directly with a synthetic plan
    # over a raw file (not loader-driven).
    _write_entities(tmp_path, [{"canonical_id": "concept:no-title", "kind": "concept", "source_path": _AGG_REL}])
    triage = AggregateRowTriage(
        "concept:no-title", "concept", _AGG_REL, False, AggregateBucket.COINED, "x", _AGG_REL, 0
    )
    plan = RetirementPlan(
        promote=(PlannedRow(triage, RetireAction.PROMOTE, _AGG_REL, 0, "entities/concepts/no-title.md"),),
        delete=(),
        reconcile=(),
        rejected=(),
    )
    report = apply_retirement(tmp_path, plan, dry_run=False)
    assert report.promoted == ()
    assert any(cid == "concept:no-title" for cid, _ in report.rejected)
    assert _entities_on_disk(tmp_path) == ["concept:no-title"]


def test_foreign_real_owner_is_left_as_shadow(tmp_path: Path) -> None:
    # A concept stub shadowed by a real, hand-authored owner (NO promoted_from marker).
    # At load it classifies `shadow`, so promote_coined routes it to the reconcile path,
    # where the missing marker means: do not delete the stub, do not touch the owner.
    # (It stays as shadow debt for `--delete-shadow` / human review.)
    _write_entities(tmp_path, [_concept("concept:1q-gain")])
    owner = tmp_path / "entities/concepts/1q-gain.md"
    owner.parent.mkdir(parents=True, exist_ok=True)
    owner.write_text("---\nid: concept:1q-gain\nkind: concept\ntitle: Hand authored\n---\nReal content.\n", "utf-8")
    report = _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert "concept:1q-gain" not in report.promoted
    assert "Real content." in owner.read_text(encoding="utf-8")  # owner untouched
    assert _entities_on_disk(tmp_path) == ["concept:1q-gain"]  # stub retained, not clobbered


def test_idempotent_second_run_is_noop(tmp_path: Path) -> None:
    _write_entities(tmp_path, [_concept("concept:1q-gain")])
    _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    report2 = _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert report2.promoted == ()
    assert report2.deleted == ()


def test_crash_recovery_completes_stranded_promotion(tmp_path: Path) -> None:
    # Simulate a crash AFTER the owner was written (with our marker) but BEFORE the
    # entry was deleted. A single --promote-coined rerun must delete the stranded entry.
    _write_entities(tmp_path, [_concept("concept:1q-gain")])
    owner = tmp_path / "entities/concepts/1q-gain.md"
    owner.parent.mkdir(parents=True, exist_ok=True)
    owner.write_text(
        f"---\nid: concept:1q-gain\nkind: concept\ntitle: x\npromoted_from: {_AGG_REL}\n---\n\nstub\n", "utf-8"
    )
    report = _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert "concept:1q-gain" in report.promoted
    assert _entities_on_disk(tmp_path) == []  # stranded entry now removed


def test_promote_preserves_description_as_owner_body(tmp_path: Path) -> None:
    _write_entities(
        tmp_path,
        [
            {
                "canonical_id": "concept:apoptosis",
                "kind": "concept",
                "title": "Apoptosis",
                "description": "Programmed cell death relevant to MM survival signaling.",
                "source_path": _AGG_REL,
            }
        ],
    )
    report = _run(tmp_path, dry_run=False, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert report.promoted == ("concept:apoptosis",)
    text = (tmp_path / "entities/concepts/apoptosis.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, _frontmatter, body = text.split("---\n", 2)
    assert "Programmed cell death relevant to MM survival signaling." in body
    assert "Programmed cell death" not in _frontmatter  # definition is the BODY, not a frontmatter value


def test_promote_target_exists_unmarked_is_skipped_entry_retained(tmp_path: Path) -> None:
    # The promote loop's foreign-owner branch: target exists WITHOUT our promoted_from
    # marker → goes to skipped, aggregate entry is retained (no clobber).
    _write_entities(tmp_path, [_concept("concept:1q-gain")])
    owner = tmp_path / "entities/concepts/1q-gain.md"
    owner.parent.mkdir(parents=True, exist_ok=True)
    owner.write_text("---\nid: concept:1q-gain\nkind: concept\ntitle: Foreign\n---\nForeign body.\n", "utf-8")
    triage = AggregateRowTriage("concept:1q-gain", "concept", _AGG_REL, False, AggregateBucket.COINED, "x", _AGG_REL, 0)
    plan = RetirementPlan(
        promote=(PlannedRow(triage, RetireAction.PROMOTE, _AGG_REL, 0, "entities/concepts/1q-gain.md"),),
        delete=(),
        reconcile=(),
        rejected=(),
    )
    report = apply_retirement(tmp_path, plan, dry_run=False)
    assert report.promoted == ()
    assert "Foreign body." in owner.read_text(encoding="utf-8")  # foreign owner untouched
    assert any(cid == "concept:1q-gain" for cid, _ in report.skipped)
    assert _entities_on_disk(tmp_path) == ["concept:1q-gain"]  # aggregate entry retained
