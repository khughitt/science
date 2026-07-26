from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from science_tool.consolidation import build_decision_material, mark_superseded
from science_tool.plan_common import (
    AllSupersessionMembers, ExplicitSupersessionIds, StateFingerprint, fingerprint,
)
from science_tool.supersede_plan import (
    InvalidRelation, SupersedeApplyError, SupersededChainReport, SupersedePlan, SupersedePreviewReport,
    apply_supersede_plan, derive_supersede_plan, plan_supersede,
)


def _empty_report() -> SupersedePreviewReport:
    return SupersedePreviewReport(
        chains=[], non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
        invalid_relations=[], archived_targets=[], unmanaged_targets=[], unbacked_inverses=[])


def test_preview_report_forbids_execution_keys() -> None:
    rpt = _empty_report()
    assert rpt.to_mark == []
    with pytest.raises(ValueError):
        SupersedePreviewReport(chains=[], non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
                               invalid_relations=[], archived_targets=[], unmanaged_targets=[],
                               unbacked_inverses=[], applied=[])  # type: ignore[call-arg]


def test_nested_report_models_forbid_extra_keys() -> None:
    # A tampered plan cannot smuggle an unknown key past a nested model.
    with pytest.raises(ValueError):
        SupersededChainReport(survivor="a", members=["b"], linear=True, bogus=1)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        InvalidRelation(code="c", path="p", subject="s", predicate="pr", object="o",
                        message="m", extra="x")  # type: ignore[call-arg]


def test_preview_report_coerces_dicts_into_nested_models() -> None:
    rpt = SupersedePreviewReport(
        chains=[{"survivor": "a", "members": ["b"], "linear": True}],
        non_linear=[], to_mark=["b"], skipped_kinds=[], to_repair=[],
        invalid_relations=[], archived_targets=[], unmanaged_targets=[], unbacked_inverses=[])
    assert rpt.chains[0].survivor == "a"  # a typed model, not a bare dict
    with pytest.raises(ValueError):
        SupersedePreviewReport(chains=[{"survivor": "a", "members": ["b"], "linear": True, "x": 1}],
                               non_linear=[], to_mark=[], skipped_kinds=[], to_repair=[],
                               invalid_relations=[], archived_targets=[], unmanaged_targets=[],
                               unbacked_inverses=[])


def test_supersede_plan_roundtrips_and_forbids_extra() -> None:
    plan = SupersedePlan(
        schema_version=1, project_root="/p", material_version=1, preview_date="2026-07-18",
        selection=AllSupersessionMembers(kind="all"), decision_inputs_sha256="a" * 64,
        to_mark=[], to_repair=[], writes=[], preview_report=_empty_report(),
    )
    again = SupersedePlan.model_validate_json(plan.model_dump_json())
    assert again == plan

    # Verify that extra top-level keys are rejected (tampered plan protection).
    tampered = json.loads(plan.model_dump_json())
    tampered["bogus_key"] = 1
    with pytest.raises(ValidationError):
        SupersedePlan.model_validate_json(json.dumps(tampered))


def _chain(root: Path) -> None:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-b\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n---\nbody\n",
        encoding="utf-8")


def test_plan_supersede_freezes_writes_and_digest(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    assert plan.to_mark == ["interpretation:0002-b"]
    assert len(plan.writes) == 1
    w = plan.writes[0]
    assert w.role == "entity-rewrite"
    assert w.rel_path == "entities/interpretations/0002-b.md"
    # pre-state fingerprint matches the live file at preview time
    assert w.pre == fingerprint(tmp_path / w.rel_path)
    assert "status: superseded" in w.postimage
    assert plan.decision_inputs_sha256  # non-empty
    assert plan.preview_report.to_mark == ["interpretation:0002-b"]


def test_plan_supersede_post_mode_matches_the_live_file(tmp_path: Path) -> None:
    _chain(tmp_path)
    live = tmp_path / "entities" / "interpretations" / "0002-b.md"
    os.chmod(live, 0o640)  # a non-default mode a rewrite must preserve
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    w = plan.writes[0]
    assert w.post.mode == 0o640  # NOT a nominal 0o644
    assert w.pre.mode == 0o640


def test_derive_supersede_plan_matches_plan_supersede_given_the_same_material(
    tmp_path: Path,
) -> None:
    # `derive_supersede_plan`, handed the material `plan_supersede` would have built itself,
    # must produce the SAME plan -- proving the delegation in `plan_supersede` is faithful and
    # that deriving from an already-built material never re-loads or re-derives anything.
    _chain(tmp_path)
    material = build_decision_material(tmp_path)
    derived = derive_supersede_plan(
        tmp_path, material, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18"
    )
    direct = plan_supersede(
        tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18"
    )
    assert derived == direct


def _two_supersessions(root: Path) -> None:
    # Two DISJOINT linear chains, so an explicit-ids selection scoped to one chain's member leaves
    # the other chain's member untouched, and a two-write plan exercises rollback across both writes.
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-b\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n---\nbody\n",
        encoding="utf-8")
    (d / "0003-c.md").write_text(
        "---\nid: interpretation:0003-c\nkind: interpretation\ntitle: C\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0004-d\n---\nbody\n",
        encoding="utf-8")
    (d / "0004-d.md").write_text(
        "---\nid: interpretation:0004-d\nkind: interpretation\ntitle: D\nstatus: active\n---\nbody\n",
        encoding="utf-8")


def test_apply_supersede_plan_matches_legacy_apply_byte_for_byte(tmp_path: Path) -> None:
    # Build TWO identical corpora. Apply the plan to one; run the legacy `mark_superseded(apply=True)`
    # on the other. The stamped file bytes must be EXACTLY identical -- the real "replay == legacy"
    # claim, with no line-stripping. Pin the plan's preview_date to today so the `updated` line the
    # legacy clock renders and the frozen postimage agree.
    from datetime import date

    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _chain(a)
    _chain(b)
    plan = plan_supersede(a, selection=AllSupersessionMembers(kind="all"),
                          preview_date=date.today().isoformat())
    report = apply_supersede_plan(a, plan, staging_token="tkn")
    assert report["applied"] == ["interpretation:0002-b"]

    mark_superseded(b, ids=None, apply=True)
    ra = (a / "entities/interpretations/0002-b.md").read_bytes()
    rb = (b / "entities/interpretations/0002-b.md").read_bytes()
    assert ra == rb  # byte-for-byte, no normalization
    assert ra.decode("utf-8") == plan.writes[0].postimage  # plan replay is byte-exact


def test_apply_refuses_on_decision_drift(tmp_path: Path) -> None:
    # Gate A (decision digest): a change to the DECISION surface after preview -- here removing 0001-a's
    # `sci:supersedes` relation so the re-derived cohort no longer marks 0002-b -- is refused. The removed
    # relation moves the decision projection, so `decision_digest(material) != plan.decision_inputs_sha256`
    # (Gate A) fires FIRST, before Gate B re-derivation or the pre-state gate is reached. The member file
    # (0002-b) is left untouched, isolating decision drift from write-source drift (next test). (Contrast:
    # a NON-projected change like editing 0001-a's `title` leaves the digest, disposition, and writes all
    # identical and MUST NOT be refused -- `test_non_projected_field_change_does_not_move_the_digest`,
    # Task 8, pins that.)
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    a = tmp_path / "entities" / "interpretations" / "0001-a.md"
    a.write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n---\nbody\n",
        encoding="utf-8")  # supersedes relation removed -> re-derived cohort marks nothing
    with pytest.raises(SupersedeApplyError, match="corpus changed since preview"):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_apply_refuses_on_write_source_drift(tmp_path: Path) -> None:
    # Gate B (write surface): a change to the MEMBER being rewritten (0002-b's `title` -- NOT a
    # decision-projection field, so the digest and disposition are UNCHANGED and Gate A passes) is still
    # refused, because the re-derived postimage differs from the frozen write, so
    # `assert_same_surface(plan.writes, expected.writes)` (Gate B) fails FIRST -- ahead of the later
    # pre-state gate, which would independently catch it via the changed pre-fingerprint. This is the
    # drift path a non-projected change to the *rendered* file legitimately triggers.
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    b = tmp_path / "entities" / "interpretations" / "0002-b.md"
    b.write_text(b.read_text(encoding="utf-8").replace("title: B", "title: B-EDITED"), encoding="utf-8")
    with pytest.raises(SupersedeApplyError, match="declared writes differ from re-derived"):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_apply_refuses_tampered_postimage(tmp_path: Path) -> None:
    import hashlib

    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    w = plan.writes[0]
    tampered = w.postimage.replace("superseded_by: interpretation:0001-a",
                                   "superseded_by: interpretation:9999-z")
    bad_post = StateFingerprint(existed=True, type="file",
                                content_sha256=hashlib.sha256(tampered.encode()).hexdigest(),
                                mode=w.post.mode, symlink_target=None)
    plan.writes[0] = w.model_copy(update={"postimage": tampered, "post": bad_post})
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_apply_refuses_tampered_preview_report(tmp_path: Path) -> None:
    # A report key the re-derivation would not produce must be rejected even if the writes are honest.
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    bad = plan.preview_report.model_copy(update={"to_mark": ["interpretation:9999-z"]})
    plan = plan.model_copy(update={"preview_report": bad})
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_apply_refuses_absolute_rel_path_escape(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    w = plan.writes[0]
    plan.writes[0] = w.model_copy(update={"rel_path": "/etc/evil.md"})
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_apply_refuses_unsupported_schema_version(tmp_path: Path) -> None:
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    plan = plan.model_copy(update={"schema_version": 999})
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn")


def test_kill_after_entity_write_leaves_a_classifiable_state(tmp_path: Path) -> None:
    # Kill matrix -- after each entity write: the written member holds its postimage; a simulated
    # kill (BaseException) bypasses rollback, so the survivor is a declared post-state, not corrupt.
    class _Kill(BaseException):
        pass

    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"),
                          preview_date="2026-07-18")
    target = tmp_path / "entities" / "interpretations" / "0002-b.md"

    def fault(label: str) -> None:
        if label == "written:entities/interpretations/0002-b.md":
            raise _Kill()

    with pytest.raises(_Kill):
        apply_supersede_plan(tmp_path, plan, staging_token="tkn", _fault=fault)
    assert target.read_text(encoding="utf-8") == plan.writes[0].postimage  # complete post-state, no rollback


def test_apply_supersede_loads_decision_material_once(tmp_path: Path, monkeypatch) -> None:
    # C2: Gate B derives from the Gate-A-verified material, so `build_decision_material` runs exactly
    # once per apply -- the digest surface authenticated in Gate A IS the derivation surface.
    import science_tool.supersede_plan as sp

    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    calls = {"n": 0}
    real = sp.build_decision_material

    def counting(root: Path):
        calls["n"] += 1
        return real(root)

    monkeypatch.setattr(sp, "build_decision_material", counting)
    apply_supersede_plan(tmp_path, plan, staging_token="tok")
    assert calls["n"] == 1  # Gate A only; a second load would mean Gate B re-derived from fresh FS


def test_apply_refuses_material_version_mismatch(tmp_path: Path) -> None:
    # I8: a plan whose material_version does not match the current material is refused at Gate A.
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    stale = plan.model_copy(update={"material_version": plan.material_version + 1})
    with pytest.raises(SupersedeApplyError, match="material_version"):
        apply_supersede_plan(tmp_path, stale, staging_token="tok")


def test_apply_explicit_ids_subset_marks_only_that_subset(tmp_path: Path) -> None:
    # I8 (selection authenticity, positive): an explicit_ids selection applies exactly its scoped
    # rederivation -- the un-selected eligible member stays untouched, not the full sweep.
    _two_supersessions(tmp_path)
    plan = plan_supersede(
        tmp_path,
        selection=ExplicitSupersessionIds(kind="explicit_ids", ids=["interpretation:0002-b"]),
        preview_date="2026-07-18",
    )
    assert plan.to_mark == ["interpretation:0002-b"]
    apply_supersede_plan(tmp_path, plan, staging_token="tok")
    b = (tmp_path / "entities" / "interpretations" / "0002-b.md").read_text(encoding="utf-8")
    d = (tmp_path / "entities" / "interpretations" / "0004-d.md").read_text(encoding="utf-8")
    assert "status: superseded" in b
    assert "status: superseded" not in d  # the un-selected member is untouched


def test_rollback_after_first_of_two_entity_writes_restores_surface(tmp_path: Path) -> None:
    # I8: a CAUGHT failure (not a kill) after the first of two writes rolls BOTH members back to pre.
    _two_supersessions(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    assert len(plan.writes) == 2
    first_rel = plan.writes[0].rel_path
    before = {w.rel_path: (tmp_path / w.rel_path).read_bytes() for w in plan.writes}

    def fault(label: str) -> None:
        if label == f"written:{first_rel}":
            raise RuntimeError("boom after first write")  # Exception -> caught -> rollback runs

    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, plan, staging_token="tok", _fault=fault)
    for rel, data in before.items():
        assert (tmp_path / rel).read_bytes() == data  # both fully restored, no half-applied surface


def test_crlf_body_normalized_identically_across_preview_applyplan_and_legacy(tmp_path: Path) -> None:
    # I4 / design §9: characterize body normalization across the THREE writer routes -- preview
    # (plan_supersede), saved-plan apply (apply_supersede_plan), and legacy apply
    # (mark_superseded(apply=True)). A CRLF body is folded to the writer's normal form identically by
    # all three. NOT a full preservation claim -- CRLF is normalized to LF, because `_render_markdown`
    # emits LF fences and an LF frontmatter block regardless, so preserving it would only produce a
    # file with mixed endings. The blank line after the closing fence IS preserved: it is authored
    # body content, and dropping it put an unrequested diff in every `entity edit`.
    def seed(root: Path) -> None:
        (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
        d = root / "entities" / "interpretations"
        d.mkdir(parents=True)
        (d / "0001-a.md").write_bytes(
            b"---\r\nid: interpretation:0001-a\r\nkind: interpretation\r\ntitle: A\r\nstatus: active\r\n"
            b"relations:\r\n  - predicate: sci:supersedes\r\n    target: interpretation:0002-b\r\n---\r\n\r\nbody\r\n")
        (d / "0002-b.md").write_bytes(
            b"---\r\nid: interpretation:0002-b\r\nkind: interpretation\r\ntitle: B\r\nstatus: active\r\n---\r\n\r\nbody line\r\n")

    rel = "entities/interpretations/0002-b.md"
    root_p = tmp_path / "preview"
    root_p.mkdir()
    seed(root_p)
    plan = plan_supersede(root_p, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    preview_body = plan.writes[0].postimage.split("---\n", 2)[2]           # preview route
    apply_supersede_plan(root_p, plan, staging_token="tok")
    applied_body = (root_p / rel).read_text(encoding="utf-8").split("---\n", 2)[2]  # apply-plan route
    root_l = tmp_path / "legacy"
    root_l.mkdir()
    seed(root_l)
    mark_superseded(root_l, ids=None, apply=True)
    legacy_body = (root_l / rel).read_text(encoding="utf-8").split("---\n", 2)[2]   # legacy apply route
    assert preview_body == applied_body == legacy_body                    # identical normal form
    assert "\r" not in applied_body                                       # CRLF normalized to LF
    assert applied_body == "\nbody line\n"                                # blank line after fence kept


def test_apply_supersede_refuses_project_root_mismatch(tmp_path: Path) -> None:
    # design §9 (drift rejection): a plan whose project_root does not match the target is refused.
    _chain(tmp_path)
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    other = plan.model_copy(update={"project_root": str(tmp_path / "elsewhere")})
    with pytest.raises(SupersedeApplyError):
        apply_supersede_plan(tmp_path, other, staging_token="tok")


def test_apply_supersede_refuses_report_hiding_a_blocker(tmp_path: Path) -> None:
    # design §9 (report binding): a plan whose preview_report hides a blocker (an unbacked inverse) is
    # refused at Gate B -- the re-derived report still carries it.
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(  # no supersedes edge -- so 0002-b's inverse is UNBACKED
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n"
        "superseded_by: interpretation:0001-a\n---\nbody\n", encoding="utf-8")
    plan = plan_supersede(tmp_path, selection=AllSupersessionMembers(kind="all"), preview_date="2026-07-18")
    assert plan.preview_report.unbacked_inverses  # the blocker is surfaced at preview
    tampered = plan.model_copy(update={
        "preview_report": plan.preview_report.model_copy(update={"unbacked_inverses": []})})
    with pytest.raises(SupersedeApplyError, match="preview report"):
        apply_supersede_plan(tmp_path, tampered, staging_token="tok")
